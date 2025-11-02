"""Northstar FastAPI Orchestrator - AI-powered experimentation platform."""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from metorial import Metorial
from openai import AsyncOpenAI
from github import Github
import os
import json
import re
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from captain_client import CaptainClient
from repo_indexer import (
    clone_repository,
    get_indexable_files,
    read_key_files,
    analyze_repository_structure,
    prepare_file_for_captain
)

import db_operations
from pr_creator import PRCreator
import logging

load_dotenv()

# Configure logging to show INFO level messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Output to console
    ]
)
logger = logging.getLogger(__name__)
logger.info("🚀 Northstar backend starting up...")

app = FastAPI(
    title="Northstar API",
    description="Autonomous AI agent for product experimentation",
    version="0.1.0"
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Metorial, OpenAI, and Captain
metorial = Metorial(api_key=os.getenv("METORIAL_API_KEY"))
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
slack_deployment_id = os.getenv("SLACK_DEPLOYMENT_ID")
github_deployment_id = os.getenv("GITHUB_DEPLOYMENT_ID", "srv_0mg8iy70b29Y2sPqULfav8")
northstar_mcp_deployment_id = os.getenv("NORTHSTAR_DEPLOYMENT_ID")  # Updated to match .env
posthog_deployment_id = os.getenv("POSTHOG_DEPLOYMENT_ID")  # PostHog analytics MCP
slack_oauth_session_id = os.getenv("SLACK_OAUTH_SESSION_ID")  # Global Slack OAuth session

# Initialize Captain client (optional - will be None if not configured)
try:
    captain = CaptainClient()
except ValueError:
    captain = None
    print("Warning: Captain not configured - knowledge base features disabled")


async def fetch_repository_context(repo_fullname: str, active_repo: Optional[Dict[str, Any]] = None) -> str:
    """
    Fetch repository code context from GitHub to understand the codebase.
    
    Options:
    1. If GITHUB_TOKEN is set: Fetches code from GitHub API
    2. If GITHUB_TOKEN is not set: Returns instructions for providing code directly
    
    Returns a formatted string with repository structure and key files WITH FULL CODE CONTENT.
    """
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        return f"""Repository: {repo_fullname}
Note: GITHUB_TOKEN not set. To analyze your codebase:
Option 1: Set GITHUB_TOKEN in .env to automatically fetch from GitHub
Option 2: Provide codebase_context in the request with your code
Option 3: The system will generate generic proposals without code analysis."""
    
    try:
        g = Github(github_token)
        repo = g.get_repo(repo_fullname)
        base_branch = active_repo.get("base_branch", "main") if active_repo else "main"
        
        # Get repository info
        context_parts = [
            f"Repository: {repo_fullname}",
            f"Description: {repo.description or 'No description'}",
            f"Language: {repo.language or 'Unknown'}",
            f"Default Branch: {base_branch}",
            f"\n=== Repository Structure ==="
        ]
        
        # Get full directory tree
        def get_tree_recursive(path: str, max_depth: int = 3, current_depth: int = 0) -> List[str]:
            """Recursively get file tree structure."""
            if current_depth >= max_depth:
                return []
            
            tree_items = []
            try:
                contents = repo.get_contents(path, ref=base_branch)
                if not isinstance(contents, list):
                    return []
                
                for content in contents:
                    if content.type == "file" and not content.name.startswith('.'):
                        tree_items.append(f"{path}/{content.name}" if path else content.name)
                    elif content.type == "dir" and not content.name.startswith('.') and current_depth < 2:
                        tree_items.extend(get_tree_recursive(
                            f"{path}/{content.name}" if path else content.name,
                            max_depth,
                            current_depth + 1
                        ))
            except Exception:
                pass
            return tree_items
        
        try:
            file_tree = get_tree_recursive("")
            context_parts.append("\nComplete File Tree:")
            for f in sorted(file_tree)[:50]:  # Show up to 50 files in tree
                context_parts.append(f"  - {f}")
        except Exception as e:
            context_parts.append(f"Could not list contents: {str(e)}")
        
        # Configuration files to skip or deprioritize (generated/auto-generated)
        config_files = {
            'package.json', 'package-lock.json', 'yarn.lock', 'requirements.txt', 'pyproject.toml',
            'pubspec.yaml', 'pubspec.lock', 'Podfile', 'Podfile.lock', 'composer.json', 'composer.lock',
            'tsconfig.json', 'jsconfig.json', 'vite.config.js', 'vite.config.ts', 'webpack.config.js',
            'next.config.js', 'tailwind.config.js', '.eslintrc', '.prettierrc', '.gitignore',
            'index.html', 'favicon.ico', 'robots.txt', '.env.example', 'docker-compose.yml', 'Dockerfile'
        }
        
        # File extensions for user-written source code (prioritize these)
        source_extensions = {
            '.dart', '.js', '.jsx', '.ts', '.tsx', '.py', '.java', '.kt', '.swift', '.go', 
            '.rs', '.cpp', '.c', '.h', '.hpp', '.cs', '.php', '.rb', '.scala', '.clj',
            '.vue', '.svelte', '.elm', '.hs', '.ml', '.mli'
        }
        
        # Directories that typically contain user-written source code (prioritize these)
        source_dirs = ["lib", "src", "app", "components", "pages", "screens", "views", 
                       "widgets", "services", "models", "utils", "helpers", "api", 
                       "controllers", "views", "backend", "server"]
        
        context_parts.append("\n=== USER-WRITTEN SOURCE CODE (PRIORITY) ===")
        files_read = 0
        max_files = 30  # Increased to prioritize source code
        total_chars = 0
        max_total_chars = 60000  # Increased total character limit
        
        # Helper function to check if a file is source code
        def is_source_file(file_path: str) -> bool:
            """Check if file is user-written source code (not config/generated)."""
            name = file_path.split('/')[-1]
            # Skip config files
            if name in config_files:
                return False
            # Check if it's in a source directory
            for source_dir in source_dirs:
                if f"/{source_dir}/" in f"/{file_path}/" or file_path.startswith(f"{source_dir}/"):
                    return True
            # Check file extension
            for ext in source_extensions:
                if file_path.endswith(ext):
                    return True
            return False
        
        # Helper function to recursively get source files from directory
        def get_source_files_from_dir(dir_path: str, max_depth: int = 3, current_depth: int = 0) -> List[Dict]:
            """Recursively get source files from a directory."""
            if current_depth >= max_depth:
                return []
            
            source_files = []
            try:
                contents = repo.get_contents(dir_path, ref=base_branch)
                if not isinstance(contents, list):
                    return []
                
                for content in contents:
                    if content.type == "file":
                        # Check if it's a source file
                        file_path = f"{dir_path}/{content.name}" if dir_path else content.name
                        if is_source_file(file_path) and not content.name.startswith('.'):
                            source_files.append({
                                'path': file_path,
                                'content_obj': content,
                                'depth': current_depth
                            })
                    elif content.type == "dir" and current_depth < 2:
                        # Recurse into subdirectories
                        sub_files = get_source_files_from_dir(
                            f"{dir_path}/{content.name}" if dir_path else content.name,
                            max_depth,
                            current_depth + 1
                        )
                        source_files.extend(sub_files)
            except Exception:
                pass
            return source_files
        
        # First, prioritize source code from key directories
        prioritized_files = []
        
        # Get source files from common source directories
        for source_dir in source_dirs:
            try:
                source_files = get_source_files_from_dir(source_dir)
                prioritized_files.extend(source_files)
            except Exception:
                continue
        
        # Sort by depth (shallow first) to prioritize main files
        prioritized_files.sort(key=lambda x: (x['depth'], x['path']))
        
        # Read prioritized source files
        for file_info in prioritized_files[:max_files]:
            if files_read >= max_files or total_chars >= max_total_chars:
                break
            try:
                file_content = file_info['content_obj']
                file_path = file_info['path']
                
                if file_content.size < 80000:  # 80KB limit per file
                    content_text = file_content.decoded_content.decode('utf-8')
                    file_chars = len(content_text)
                    if total_chars + file_chars <= max_total_chars:
                        context_parts.append(f"\n--- {file_path} (USER-WRITTEN CODE) ---")
                        context_parts.append(content_text)
                        files_read += 1
                        total_chars += file_chars
                    elif max_total_chars - total_chars > 5000:
                        # Include partial if we have significant space left
                        remaining = max_total_chars - total_chars
                        context_parts.append(f"\n--- {file_path} (USER-WRITTEN CODE - PARTIAL) ---")
                        context_parts.append(content_text[:remaining])
                        files_read += 1
                        total_chars += remaining
            except Exception:
                continue
        
        # If we haven't read enough, also try top-level source files
        if files_read < max_files and total_chars < max_total_chars:
            try:
                root_contents = repo.get_contents("", ref=base_branch)
                if isinstance(root_contents, list):
                    root_source_files = [
                        c for c in root_contents 
                        if c.type == "file" and is_source_file(c.name) and not c.name.startswith('.')
                    ]
                    for file_content in root_source_files[:10]:  # Limit top-level files
                        if files_read >= max_files or total_chars >= max_total_chars:
                            break
                        try:
                            if file_content.size < 50000:
                                content_text = file_content.decoded_content.decode('utf-8')
                                file_chars = len(content_text)
                                if total_chars + file_chars <= max_total_chars:
                                    context_parts.append(f"\n--- {file_content.name} (USER-WRITTEN CODE) ---")
                                    context_parts.append(content_text)
                                    files_read += 1
                                    total_chars += file_chars
                        except Exception:
                            continue
            except Exception:
                pass
        
        # Get commit info for context
        try:
            commits = repo.get_commits(base_branch, per_page=5)
            context_parts.append("\n=== Recent Commits ===")
            for commit in commits:
                context_parts.append(f"  - {commit.commit.message.split(chr(10))[0][:120]}")
        except Exception:
            pass
        
        context_parts.append(f"\n=== END OF CODE CONTEXT (Read {files_read} files, {total_chars} characters) ===")
        
        return "\n".join(context_parts)
    
    except Exception as e:
        return f"Repository: {repo_fullname}\nError fetching repository context: {str(e)}"


# Request/Response Models
class OAuthCompleteRequest(BaseModel):
    session_id: str


class ProposeExperimentRequest(BaseModel):
    oauth_session_id: str
    codebase_context: Optional[str] = None  # Optional: Direct codebase context to analyze


class ExecuteExperimentRequest(BaseModel):
    proposal_id: str
    instruction: str
    update_block: str
    oauth_session_id: str
    repo_fullname: Optional[str] = None
    file_path: Optional[str] = None
    base_branch: Optional[str] = None


class UpdateProposalStatusRequest(BaseModel):
    proposal_id: str
    status: str  # pending, approved, rejected, executing, completed


class ConnectRepositoryRequest(BaseModel):
    repo_fullname: str  # Format: "owner/repo"
    default_branch: str = "main"
    base_branch: str = "main"


class ApproveProposalRequest(BaseModel):
    proposal_id: str
    update_block: str  # Fast Apply format code update block


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Northstar API",
        "version": "0.1.0"
    }


@app.get("/oauth/start")
async def start_oauth():
    """
    Step 1: Create OAuth session for Slack.
    Frontend should redirect user to auth_url.
    """
    oauth_session = metorial.oauth.sessions.create(
        server_deployment_id=slack_deployment_id
    )
    return {
        "session_id": oauth_session.id,
        "auth_url": oauth_session.url
    }


@app.get("/oauth/complete")
async def complete_oauth(session_id: str):
    """
    Step 2: Wait for OAuth completion after user authorizes.
    """
    try:
        await metorial.oauth.wait_for_completion(session_id)
        return {
            "status": "success",
            "message": "OAuth complete",
            "session_id": session_id
        }
    except Exception as e:
        # If OAuth is already complete or session doesn't exist, still return success
        error_msg = str(e).lower()
        if "already" in error_msg or "complete" in error_msg or "not found" in error_msg:
            return {
                "status": "success",
                "message": "OAuth already complete or session valid",
                "session_id": session_id
            }
        raise HTTPException(status_code=500, detail=f"OAuth completion error: {str(e)}")


@app.post("/northstar/propose")
async def propose_experiment(req: ProposeExperimentRequest):
    """
    Generate an experiment proposal using Metorial + Northstar MCP.

    This uses the AI to:
    1. Call the propose_experiment MCP tool (if deployed) or generate directly
    2. Save the proposal to Supabase
    3. Return a structured proposal
    """
    try:
        # Get active repository
        active_repo = db_operations.get_active_repository()
        repo_id = active_repo.get("id") if active_repo else None
        repo_fullname = active_repo.get("repo_fullname") if active_repo else "unknown/unknown"

        # Determine which deployments to use
        deployments = [{
            "serverDeploymentId": slack_deployment_id,
            "oauthSessionId": req.oauth_session_id
        }]

        # Add Northstar MCP if deployed
        if northstar_mcp_deployment_id:
            deployments.append({
                "serverDeploymentId": northstar_mcp_deployment_id
            })

        # Generate proposal - try with MCP tool first, fallback to direct generation
        # First, get repository code context
        if req.codebase_context:
            repo_context = f"""
Repository: {repo_fullname}
User-provided codebase context:
{req.codebase_context}
"""
        else:
            repo_context = await fetch_repository_context(repo_fullname, active_repo)
        
        # Validate that we have actual code context
        if not repo_context or len(repo_context.strip()) < 100:
            error_msg = f"Insufficient codebase context. Repository context is too short ({len(repo_context) if repo_context else 0} chars)."
            if "GITHUB_TOKEN not set" in repo_context:
                error_msg += " Please set GITHUB_TOKEN in your backend environment variables to automatically fetch code from GitHub, or provide codebase_context in the request."
            else:
                error_msg += " Please ensure GITHUB_TOKEN is set in the backend environment, or provide codebase_context in the request."
            raise HTTPException(
                status_code=400,
                detail=error_msg
            )
        
        # Check if repo_context looks like an error message instead of actual code
        if "GITHUB_TOKEN not set" in repo_context or "Note:" in repo_context:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot fetch repository code. {repo_context}. Please set GITHUB_TOKEN in your backend environment variables, or provide codebase_context in the request with the actual repository code."
            )
        
        try:
            if northstar_mcp_deployment_id:
                # Try to use propose_experiment tool
                result = await metorial.run(
                    client=openai_client,
                    message=f"""
                    CALL THE propose_experiment TOOL IMMEDIATELY. The codebase context is provided below - you don't need to fetch anything, just analyze what's provided.
                    
                    STEP 1: Call propose_experiment tool RIGHT NOW with these parameters:
                    {{
                      "codebase_context": "{repo_context[:4000]}...",
                      "repo_fullname": "{repo_fullname}"
                    }}
                    
                    IMPORTANT: The codebase_context parameter ALREADY CONTAINS the actual repository code below. You don't need to fetch anything - the code is provided for you. Just analyze it.
                    
                    Full codebase context (first 4000 chars):
                    {repo_context[:4000]}
                    
                    STEP 2: After calling the tool, analyze the codebase_context that was provided and generate a proposal with ACTUAL UI/VISUAL CODE CHANGES based on the actual code you see.
                    
                    CRITICAL FOCUS: UI/VISUAL ADJUSTMENTS ONLY - analyze the CSS, Tailwind classes, inline styles, and component styling in the codebase_context provided above.
                    
                    STEP 3: Return ONLY valid JSON (no explanations, no code fences, no text before/after):
                    
                    {{"proposal_id": "exp-unique", "idea_summary": "Specific UI/visual improvement based on actual styling code analysis (e.g., 'Improve button hover states', 'Fix spacing inconsistencies', 'Enhance visual hierarchy')", "rationale": "Detailed explanation of the UI/visual problem found in the styling code (what styling issue exists, why it hurts the user experience visually, how the change will improve visual design)", "expected_impact": {{"metric": "click_rate", "delta_pct": 0.05}}, "technical_plan": [{{"file": "actual/path/to/style/file.ext (CSS, JSX, TSX, etc.)", "action": "Specific UI/styling change description"}}], "update_block": "ACTUAL UI/STYLING CODE CHANGES in Fast Apply format with +/- markers showing specific styling modifications (CSS properties, Tailwind classes, inline styles, component props) - NO placeholders, NO instructions, JUST ACTUAL STYLING CODE", "category": "ui_optimization", "confidence": 0.8}}
                    
                    NOTE: The proposal_id field will be ignored - a unique ID will be generated automatically. Just use "exp-unique" as a placeholder.
                    
                    IMPORTANT: Return ONLY the JSON object, nothing else. No explanations, no code fences, no markdown. Just pure valid JSON that can be parsed directly.
                    The update_block MUST contain actual UI/styling code changes with +/- markers (CSS changes, Tailwind class modifications, style prop updates), NOT instructions or placeholders.
                    Focus ONLY on visual/styling improvements that users will see.
                    """,
                    model="gpt-4o",
                    server_deployments=deployments,
                    max_steps=10
                )
            else:
                raise Exception("MCP tool not available")
        except Exception as mcp_error:
            # Fallback: Generate proposal directly using GPT-4o with repository context
            result = await metorial.run(
                client=openai_client,
                message=f"""
                YOU ARE A UI/VISUAL DESIGN-FOCUSED CODE ANALYST. Your PRIMARY focus is identifying VISUAL DESIGN AND USER INTERFACE PROBLEMS in the actual code and proposing MEASURABLE UI/VISUAL IMPROVEMENTS. FOCUS EXCLUSIVELY ON UI/VISUAL ADJUSTMENTS (what users SEE).
                
                REPOSITORY CONTEXT (ACTUAL CODE FROM {repo_fullname}):
                {repo_context}
                
                CRITICAL INSTRUCTIONS:
                1. IGNORE configuration files (package.json, pubspec.yaml, tsconfig.json, etc.) - these are NOT user-written code
                2. FOCUS ONLY on UI/STYLING code files (CSS, Tailwind classes, component styling, HTML structure, React/Flutter UI components)
                3. IGNORE: Functional logic, backend code, business logic, data processing, API calls, error handling logic (unless it affects UI display)
                4. ANALYZE ACTUAL STYLING/UI CODE and identify VISUAL/UI PROBLEMS:
                   
                   UI PROBLEMS (User Interface / Visual Design) - FOCUS EXCLUSIVELY ON THESE:
                   - Poor visual hierarchy (important elements not emphasized, need better sizing/spacing)
                   - Inconsistent spacing/padding (messy layouts, elements too close/far)
                   - Poor typography (hard to read, wrong sizes, bad font choices)
                   - Inconsistent color scheme (colors don't work together, poor contrast)
                   - Cluttered layouts (too much information, poor organization, need whitespace)
                   - Missing visual polish (buttons without hover states, no transitions, no shadows)
                   - Poor responsive design (doesn't work on different screen sizes, breaks on mobile)
                   - Unclear visual feedback (buttons don't look clickable, no hover states, no active states)
                   - Inconsistent styling (different styles for similar elements, need design system)
                   - Poor contrast (hard to read text, accessibility issues)
                   - Missing visual cues (no icons, unclear what's clickable, no loading indicators)
                   - Bad layouts (elements overlapping, misaligned, need better grid/flexbox)
                   - Missing design system (inconsistent components, repeated styles)
                   - Poor button styling (no hover/active states, bad colors, wrong sizes)
                   - Bad form styling (input fields hard to see, labels unclear, validation unclear)
                   - Missing animations (transitions feel abrupt, no micro-interactions)
                   - Poor card/container styling (no shadows, no borders, no visual separation)
                
                YOUR ANALYSIS PROCESS:
                
                Step 1: UNDERSTAND THE VISUAL UI STRUCTURE
                - Analyze the UI/styling code structure (CSS, component styling, layout code)
                - Identify visual elements and their current styling (buttons, forms, cards, containers, text, spacing)
                - Look for visual inconsistencies and styling patterns across the codebase
                - Understand the current visual design system (if any) and identify gaps
                
                Step 2: IDENTIFY SPECIFIC UI/VISUAL PROBLEMS IN THE CODE
                - Analyze UI/STYLING code: CSS files, Tailwind classes, inline styles, component styling props
                - Find styling inconsistencies: same elements styled differently across the app
                - Identify poor visual design: cluttered layouts, poor spacing, bad typography, inconsistent colors
                - Look for missing visual polish: no hover states, no transitions, no shadows, no borders
                - Check for visual hierarchy issues: important elements not emphasized, poor sizing/spacing
                - Find typography problems: hard to read, wrong sizes, bad font choices, poor contrast
                - Identify color scheme issues: colors don't work together, poor contrast, inconsistent palette
                - Look for button/form styling problems: no hover states, bad colors, wrong sizes, unclear styling
                - Check responsive design: layouts that don't work on mobile/tablet, missing breakpoints
                - Find layout issues: elements overlapping, misaligned, need better grid/flexbox
                - Identify missing visual feedback: no loading indicators, no hover effects, no active states
                - Check card/container styling: no shadows, no borders, no visual separation
                
                Step 3: PROPOSE MEASURABLE UI/VISUAL IMPROVEMENTS (UI/VISUAL ADJUSTMENTS ONLY)
                - Choose ONE specific, high-impact UI/VISUAL improvement based on actual styling/UI code you analyzed
                - FOCUS EXCLUSIVELY ON VISUAL/UI improvements (styling changes, layout adjustments, visual design)
                - Make sure your change is CORRECT and will actually work (use proper syntax, match existing patterns)
                - Focus on improvements that users will VISUALLY NOTICE immediately
                - REQUIRED: UI/VISUAL improvements (what users see) - styling, layout, colors, typography, visual hierarchy:
                  * Improve visual hierarchy with better sizing, spacing, or colors
                  * Add consistent spacing/padding for cleaner layouts
                  * Improve typography (font sizes, weights, colors for better readability)
                  * Add hover states, active states, and transitions for buttons/interactive elements
                  * Improve color scheme (better contrast, consistent palette, accessibility)
                  * Clean up cluttered layouts (better organization, whitespace, card design)
                  * Add visual polish (shadows, borders, rounded corners, transitions)
                  * Improve responsive design (mobile breakpoints, flexbox/grid improvements)
                  * Fix styling inconsistencies (make similar elements look the same)
                  * Add visual feedback (loading indicators, hover effects, active states)
                  * Improve button styling (better colors, sizes, hover/active states)
                  * Improve form styling (better input fields, labels, validation styling)
                - SECONDARY: UX improvements (what users experience):
                  * Add loading spinner while data loads
                  * Add error message display
                  * Improve error messages to be user-friendly
                  * Add empty states
                  * Improve form validation feedback
                
                Step 4: WRITE CORRECT, WORKING UI/STYLING CODE
                - Your UI/styling changes MUST be syntactically correct and match the existing code style
                - Use actual CSS classes, Tailwind classes, style props, component names from the code you analyzed
                - For CSS: Match existing patterns, use correct selectors, proper property syntax
                - For Tailwind: Use correct class names, match existing Tailwind patterns
                - For React/component styling: Use correct style props, className props, or styled-component patterns
                - For Flutter/Dart: Pay EXTREME attention to UI/styling code structure:
                  * Widget style properties go INSIDE widget constructors (e.g., ElevatedButton(style: styleFrom(...)))
                  * Button style properties go in ElevatedButton.styleFrom() (e.g., backgroundColor, foregroundColor, overlayColor)
                  * Style properties NEVER go in setState() blocks - only state variables
                  * Preserve the exact structure of the original UI code - only modify styling properties
                - Test your styling mentally - will this actually work and improve the visual appearance?
                
                EXAMPLE OF CORRECT Flutter update_block:
                If you want to add overlayColor to a button, it goes in the styleFrom() call:
                
                  ElevatedButton(
                    onPressed: () {{}},
                    style: ElevatedButton.styleFrom(
                      elevation: 0,
                      foregroundColor: Colors.white,
                +     overlayColor: MaterialStateProperty.all(Colors.black12),
                      backgroundColor: Color.fromRGBO(255, 191, 99, 1),
                    ),
                  ),
                
                WRONG (DO NOT DO THIS):
                  setState(() {{
                -     errorText = 'One or more fields are empty!';
                +     onPrimary: Colors.white,  // THIS IS WRONG - onPrimary doesn't go in setState!
                  }});
                
                Return a JSON object with this structure:
                {{
                    "proposal_id": "exp-unique",
                    "idea_summary": "Specific UX/UI improvement based on actual code - e.g., 'Add loading state to prevent blank screen during auth' or 'Improve visual hierarchy with better spacing' or 'Add hover states for better interactivity'",
                    "rationale": "DETAILED explanation of the UX/UI problem you found in the code: What user flow or visual design was affected? What specific code has the issue? Why does it hurt UX/UI? How will your change improve the user experience or visual design? Reference specific files, functions, components, and code patterns you saw.",
                    "expected_impact": {{"metric": "user_satisfaction", "delta_pct": 0.10}},
                    "technical_plan": [
                        {{"file": "actual/path/to/file.ext", "action": "Specific UX/UI improvement - e.g., 'Add loading indicator during async operation' or 'Improve button styling with hover states' or 'Fix layout spacing for better visual hierarchy'"}}
                    ],
                    "update_block": "FINAL CODE WITH INLINE CHANGES - SIMPLE UNIFIED DIFF FORMAT:\\n\\nYou MUST show the FINAL, COMPLETE code block with inline +/- markers. NO git diff headers (no 'diff --git', 'index', '---', '+++' lines). Just show code with +/- markers. Include 5-10 lines of context before and after. For Flutter, ensure changes are in correct locations (e.g., button properties in styleFrom, not in setState).",
                    "category": "user_experience",
                    "confidence": 0.80
                }}
                
                CRITICAL REQUIREMENTS FOR update_block (NO EXCEPTIONS):
                - ABSOLUTELY NO PLACEHOLDER TEXT like "[Show code...]", "[Your changes here]", "... existing code ..."
                - NO git diff headers (NO "diff --git", "index", "---", "+++" lines - these will cause parsing errors)
                - MUST use SIMPLE unified diff format with +/- markers only - NO git diff headers
                - Show ONLY the code with +/- markers indicating changes
                - MUST contain ACTUAL, REAL code from the repository context you analyzed
                - MUST include 5-10 lines of REAL context before and after the changes
                - MUST be syntactically correct and match the language/framework patterns (React, Flutter, Dart, JavaScript, etc.)
                - MUST use real function names, class names, component names, variable names, CSS class names from the ACTUAL code
                - For Flutter/Dart: Ensure code changes are in the correct location (e.g., onPrimary goes in ElevatedButton.styleFrom(), NOT in setState())
                - MUST preserve proper indentation and code structure
                
                EXAMPLE FORMAT FOR update_block (Flutter):
                // DO NOT include git diff headers!
                // Just show code with +/- markers:
                
                  const SizedBox(height: 32),
                + RichText(
                +   textAlign: TextAlign.center,
                +   ...
                + ),
                  ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      elevation: 0,
                      foregroundColor: Colors.white,
                +     overlayColor: MaterialStateProperty.all(Colors.black12),
                      backgroundColor: Color.fromRGBO(255, 191, 99, 1),
                    ),
                  ),
                
                WRONG FORMAT (DO NOT USE):
                - diff --git a/lib/file.dart b/lib/file.dart
                - index ...
                - --- a/lib/file.dart
                - +++ b/lib/file.dart
                - @@ -53,11 +53,13 @@
                
                Return ONLY valid JSON, no markdown or extra text.
                """,
                model="gpt-4o",
                server_deployments=deployments if slack_deployment_id else [],
                max_steps=8
            )

        # Parse the proposal JSON from the result
        proposal_text = result.text
        
        # Remove markdown code fences if present
        json_text = re.sub(r'^```(?:json)?\s*\n', '', proposal_text.strip(), flags=re.MULTILINE)
        json_text = re.sub(r'\n```\s*$', '', json_text.strip(), flags=re.MULTILINE)
        
        # Try to extract JSON object from the text
        def extract_json_object(text):
            """Extract the first complete JSON object from text by matching braces."""
            # First, try to extract JSON from code fences (```json ... ```)
            code_fence_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
            code_fence_match = re.search(code_fence_pattern, text, re.DOTALL)
            if code_fence_match:
                potential_json = code_fence_match.group(1)
                try:
                    json.loads(potential_json)  # Validate it's valid JSON
                    return potential_json
                except:
                    pass  # Continue to other extraction methods
            
            # Look for JSON object starting with {
            start_idx = text.find('{')
            if start_idx == -1:
                return None
            
            brace_count = 0
            in_string = False
            escape_next = False
            
            for i in range(start_idx, len(text)):
                char = text[i]
                
                if escape_next:
                    escape_next = False
                    continue
                
                if char == '\\':
                    escape_next = True
                    continue
                
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                
                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            extracted = text[start_idx:i+1]
                            # Validate it's reasonable JSON (has proposal_id or idea_summary)
                            if 'proposal_id' in extracted or 'idea_summary' in extracted:
                                return extracted
            
            return None
        
        json_str = extract_json_object(json_text)
        
        if not json_str:
            # Try regex pattern matching for JSON
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', json_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
            else:
                # Last resort: try to find any { ... } block
                json_match = re.search(r'\{.*\}', json_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                else:
                    json_str = json_text
        
        # Clean up common issues
        # Remove trailing commas before closing braces/brackets
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
        # Fix invalid escape sequences
        json_str = json_str.replace('\\$', '\\\\$')
        # Remove any leading/trailing whitespace
        json_str = json_str.strip()
        
        try:
            proposal_json = json.loads(json_str)
        except json.JSONDecodeError as e:
            # Try to fix common JSON issues and retry
            try:
                # First, try to fix unterminated strings by properly escaping control characters
                # Replace unescaped newlines, carriage returns, tabs in string values
                # We'll use a more careful approach - find string values and escape them
                
                # Strategy: Find all string values and ensure they're properly escaped
                # Pattern: "field": "value" where value might contain unescaped characters
                
                # Fix common issues:
                # 1. Unescaped newlines in string values (should be \n)
                # 2. Unescaped quotes in string values (should be \")
                # 3. Unescaped backslashes (should be \\)
                
                # Use a simple approach: try to fix the update_block field specifically
                # since that's most likely to have code with unescaped characters
                if '"update_block"' in json_str:
                    # Try to extract and re-escape the update_block value
                    # Pattern: "update_block": "value"
                    update_block_pattern = r'"update_block"\s*:\s*"([^"]*(?:"[^"]*")*[^"]*)"'
                    
                    # Try with more flexible pattern to handle multi-line strings
                    update_block_pattern2 = r'"update_block"\s*:\s*"(.*?)"(?=\s*[,}])'
                    match = re.search(update_block_pattern2, json_str, re.DOTALL)
                    if not match:
                        # Try pattern that matches until next field or end
                        update_block_pattern3 = r'"update_block"\s*:\s*"([^"]*(?:"[^"]*")*[^"]*?)(?:"\s*[,}])'
                        match = re.search(update_block_pattern3, json_str, re.DOTALL)
                    
                    if match:
                        update_block_value = match.group(1)
                        # Properly escape the update_block value for JSON
                        # Need to escape in the right order: backslashes first, then quotes
                        escaped_value = (
                            update_block_value
                            .replace('\\', '\\\\')  # Escape backslashes first
                            .replace('"', '\\"')     # Escape quotes
                            .replace('\n', '\\n')    # Escape newlines
                            .replace('\r', '\\r')    # Escape carriage returns
                            .replace('\t', '\\t')    # Escape tabs
                        )
                        # Replace in original JSON
                        json_str = json_str[:match.start(1)] + escaped_value + json_str[match.end(1):]
                    else:
                        # If we couldn't match with regex, try a different approach
                        # Find the update_block field and manually escape everything until the next quote
                        # This handles cases where the string value has unescaped newlines
                        update_block_start = json_str.find('"update_block"')
                        if update_block_start != -1:
                            # Find the opening quote after the colon
                            colon_pos = json_str.find(':', update_block_start)
                            if colon_pos != -1:
                                quote_start = json_str.find('"', colon_pos)
                                if quote_start != -1:
                                    # Now find where the string should end
                                    # Look for the next unescaped quote
                                    quote_end = quote_start + 1
                                    escaped = False
                                    while quote_end < len(json_str):
                                        if json_str[quote_end] == '\\' and not escaped:
                                            escaped = True
                                            quote_end += 1
                                            continue
                                        if json_str[quote_end] == '"' and not escaped:
                                            # Found the end of the string
                                            break
                                        if escaped:
                                            escaped = False
                                        # If we hit a newline that's not escaped, we have a problem
                                        # Try to find the next quote after this
                                        quote_end += 1
                                    
                                    # Extract and escape the value
                                    update_block_value = json_str[quote_start+1:quote_end]
                                    escaped_value = (
                                        update_block_value
                                        .replace('\\', '\\\\')  # Escape backslashes first
                                        .replace('"', '\\"')     # Escape quotes
                                        .replace('\n', '\\n')    # Escape newlines
                                        .replace('\r', '\\r')    # Escape carriage returns
                                        .replace('\t', '\\t')    # Escape tabs
                                    )
                                    # Replace in original JSON
                                    json_str = json_str[:quote_start+1] + escaped_value + json_str[quote_end:]
                
                # Also try to fix other common issues
                # Remove control characters that might break JSON (but keep \n, \r, \t if they're escaped)
                json_str_clean = json_str
                
                try:
                    proposal_json = json.loads(json_str_clean)
                except json.JSONDecodeError as e2:
                    # Last resort: try with minimal fixes
                    # Just remove truly problematic control characters (not \n \r \t if escaped)
                    json_str_minimal = ''.join(
                        char if ord(char) >= 32 or char in '\n\r\t' or (char == '\\' and i+1 < len(json_str_clean) and json_str_clean[i+1] in 'nrt"\\')
                        else ''
                        for i, char in enumerate(json_str_clean)
                    )
                    try:
                        proposal_json = json.loads(json_str_minimal)
                    except json.JSONDecodeError:
                        # Log the error with more context
                        error_detail = f"Failed to parse proposal JSON: {str(e)}. Attempted fixes also failed: {str(e2)}. Raw result (first 2000 chars): {proposal_text[:2000]}"
                        raise HTTPException(
                            status_code=500,
                            detail=error_detail
                        )
            except HTTPException:
                raise
            except Exception as fix_error:
                # If fixes fail, raise original error
                error_detail = f"Failed to parse proposal JSON: {str(e)}. Fix attempt failed: {str(fix_error)}. Raw result (first 2000 chars): {proposal_text[:2000]}"
                raise HTTPException(
                    status_code=500,
                    detail=error_detail
                )

        # Generate a unique proposal_id based on timestamp and repository
        import time
        import hashlib
        timestamp = int(time.time())
        
        # Create a unique proposal ID based on timestamp and repo
        # Format: exp-{timestamp}-{hash}
        repo_hash = hashlib.md5(repo_fullname.encode()).hexdigest()[:6] if repo_fullname else "default"
        unique_proposal_id = f"exp-{timestamp}-{repo_hash}"
        
        # Keep AI's proposal_id as a reference, but use our unique one
        ai_proposal_id = proposal_json.get("proposal_id", "exp-001")
        update_block = proposal_json.get("update_block", "")
        
        # Clean up update_block: Remove git diff headers if present
        if update_block:
            update_lines = update_block.split('\n')
            cleaned_lines = []
            for line in update_lines:
                trimmed = line.strip()
                # Skip git diff headers
                if (trimmed.startswith('diff --git') or 
                    trimmed.startswith('index ') or 
                    (trimmed.startswith('---') and not trimmed.startswith('---/')) or
                    (trimmed.startswith('+++') and not trimmed.startswith('+++/')) or
                    re.match(r'^@@\s+-?\d+,\d+\s+\+?\d+,\d+\s+@@', trimmed)):
                    continue
                cleaned_lines.append(line)
            update_block = '\n'.join(cleaned_lines).strip()
        
        # Save proposal to Supabase with unique proposal_id
        proposal = db_operations.create_proposal(
            proposal_id=unique_proposal_id,
            idea_summary=proposal_json.get("idea_summary", ""),
            rationale=proposal_json.get("rationale", ""),
            expected_impact=proposal_json.get("expected_impact", {}),
            technical_plan=proposal_json.get("technical_plan", []),
            category=proposal_json.get("category", "general"),
            confidence=proposal_json.get("confidence", 0.5),
            repo_id=repo_id,
            update_block=update_block,
            oauth_session_id=req.oauth_session_id
        )

        # Use the actual proposal_id that was saved (may have been modified if duplicate)
        actual_proposal_id = proposal.get("proposal_id", unique_proposal_id)

        # Send Slack notification if OAuth session ID is available
        import logging
        logger = logging.getLogger(__name__)
        
        if not slack_deployment_id:
            logger.info("SLACK_DEPLOYMENT_ID not set, skipping Slack notification for new proposal")
        elif not req.oauth_session_id:
            logger.info("No OAuth session ID provided, skipping Slack notification for new proposal")
        else:
            try:
                slack_message = f"New proposal: {proposal_json.get('idea_summary', 'Unknown')}\n"
                slack_message += f"ID: {actual_proposal_id}\n"
                slack_message += f"Repository: {repo_fullname}\n"
                slack_message += f"Category: {proposal_json.get('category', 'general')}\n"
                slack_message += f"Confidence: {proposal_json.get('confidence', 0.5) * 100:.0f}%"
                
                # Call send_slack_message with proper request object
                slack_req = SlackMessageRequest(message=slack_message, oauth_session_id=req.oauth_session_id)
                await send_slack_message(slack_req)
                logger.info(f"Successfully sent Slack notification for new proposal {actual_proposal_id}")
            except Exception as slack_error:
                # Don't fail the proposal creation if Slack notification fails
                logger.warning(f"Failed to send Slack notification for new proposal: {str(slack_error)}")
                logger.warning(f"OAuth session ID: {req.oauth_session_id[:20]}..." if req.oauth_session_id else "No OAuth session ID")
                logger.warning(f"Slack deployment ID: {slack_deployment_id}" if slack_deployment_id else "No Slack deployment ID")

        # Create activity log
        db_operations.create_activity_log(
            message=f"Proposed experiment: {proposal_json.get('idea_summary', 'Unknown')}",
            proposal_id=actual_proposal_id,
            log_type="info"
        )

        return {
            "status": "success",
            "proposal": proposal
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/northstar/execute")
async def execute_experiment(req: ExecuteExperimentRequest):
    """
    Execute an approved experiment using Metorial orchestration.

    This uses Metorial to:
    1. Call execute_code_change MCP tool (Morph + GitHub)
    2. Save experiment record to Supabase
    3. Post result to Slack
    4. Return PR URL
    """
    try:
        # Validate required fields for execution
        if not req.repo_fullname:
            raise HTTPException(
                status_code=400,
                detail="Repository name is required for execution"
            )
        if not req.file_path:
            raise HTTPException(
                status_code=400,
                detail="File path is required for execution"
            )
        
        base_branch = req.base_branch or "main"

        # Use MCP approach for PR creation via Northstar MCP server
        # Note: Currently using direct PR creation as fallback since MCP tools aren't being exposed
        use_direct_pr_creation = True

        # Determine which deployments to use
        deployments = [
            {
                "serverDeploymentId": slack_deployment_id,
                "oauthSessionId": req.oauth_session_id
            },
            {
                "serverDeploymentId": github_deployment_id
            },
            {
                "serverDeploymentId": northstar_mcp_deployment_id
            }
        ]

        # Create experiment record in Supabase
        experiment = db_operations.create_experiment(
            proposal_id=req.proposal_id,
            instruction=req.instruction,
            update_block=req.update_block,
            oauth_session_id=req.oauth_session_id
        )

        # Fallback: Direct PR creation (if MCP is unavailable)
        if use_direct_pr_creation:
            import logging
            logger = logging.getLogger(__name__)

            logger.info(f"Using direct PR creation for experiment {req.proposal_id}")

            try:
                # Create PR directly
                pr_creator = PRCreator()
                pr_result = pr_creator.create_pr(
                    repo_fullname=req.repo_fullname,
                    instruction=req.instruction,
                    update_block=req.update_block,
                    file_path=req.file_path,
                    base_branch=base_branch
                )

                if pr_result["status"] == "error":
                    raise Exception(pr_result.get("error", "PR creation failed"))

                pr_url = pr_result["pr_url"]
                branch = pr_result["branch_name"]

                logger.info(f"PR created: {pr_url}")

                # Update experiment with PR URL
                db_operations.update_experiment(
                    experiment_id=experiment.get("id"),
                    pr_url=pr_url,
                    status="running"
                )

                # Send Slack notification
                if slack_deployment_id and req.oauth_session_id:
                    try:
                        slack_message = f"Experiment executed\n"
                        slack_message += f"ID: {req.proposal_id}\n"
                        slack_message += f"Description: {req.instruction}\n"
                        slack_message += f"PR: {pr_url}"

                        await send_slack_message(slack_message, req.oauth_session_id)
                        logger.info(f"Slack notification sent for {req.proposal_id}")
                    except Exception as slack_error:
                        logger.warning(f"Slack notification failed: {str(slack_error)}")

                # Create activity log
                db_operations.create_activity_log(
                    message=f"Executed experiment {req.proposal_id}: {req.instruction[:50]}... PR: {pr_url}",
                    proposal_id=req.proposal_id,
                    experiment_id=experiment.get("id"),
                    log_type="success"
                )

                return {
                    "status": "success",
                    "result": f"PR created at {pr_url}",
                    "proposal_id": req.proposal_id,
                    "experiment_id": experiment.get("id"),
                    "pr_url": pr_url,
                    "branch": branch
                }

            except Exception as direct_pr_error:
                logger.error(f"Direct PR creation failed: {str(direct_pr_error)}")

                db_operations.update_experiment(
                    experiment_id=experiment.get("id"),
                    status="failed"
                )

                raise HTTPException(
                    status_code=500,
                    detail=f"PR creation failed: {str(direct_pr_error)}"
                )

        # Use Metorial with Northstar MCP to orchestrate PR creation
        # Pass repo and file_path to the execute_code_change tool
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Executing experiment {req.proposal_id}")
        logger.info(f"Repository: {req.repo_fullname}, File: {req.file_path}, Branch: {base_branch}")
        logger.info(f"Deployments: {deployments}")
        logger.info(f"NORTHSTAR_MCP_DEPLOYMENT_ID: {northstar_mcp_deployment_id}")
        logger.info(f"Total deployments count: {len(deployments)}")
        
        try:
            # Escape update_block for JSON embedding in message
            import json as json_module
            escaped_update_block = json_module.dumps(req.update_block)  # This escapes quotes and special chars
            
            # Use explicit function/tool calling approach
            # Metorial should automatically discover tools from the deployment
            result = await metorial.run(
                client=openai_client,
                message=f"""You have access to tools from the MCP server deployment {northstar_mcp_deployment_id}.

Call the execute_code_change tool with these parameters:
{{
  "instruction": {json_module.dumps(req.instruction)},
  "update_block": {escaped_update_block},
  "repo": {json_module.dumps(req.repo_fullname)},
  "file_path": {json_module.dumps(req.file_path)},
  "base_branch": {json_module.dumps(base_branch)}
}}

The tool will return JSON with a pr_url field. Extract and return only that JSON.""",
                model="gpt-4o",
                server_deployments=deployments,
                max_steps=20,
                temperature=0.1  # Lower temperature for more deterministic tool calling
            )
            
            logger.info(f"Metorial run completed. Result: {result.text[:500]}...")
            
        except Exception as mcp_error:
            logger.error(f"Error during Metorial execution: {str(mcp_error)}")
            logger.error(f"Error type: {type(mcp_error)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Update experiment status to failed
            db_operations.update_experiment(
                experiment_id=experiment.get("id"),
                status="failed"
            )
            
            raise HTTPException(
                status_code=500,
                detail=f"Failed to execute experiment: {str(mcp_error)}"
            )

        # Try to extract PR URL and branch from result
        pr_url = None
        branch = None
        
        # Log the full result for debugging
        logger.info(f"Full Metorial result text (first 2000 chars): {result.text[:2000]}")
        
        # Look for PR URL in the result text
        pr_url_match = re.search(r'https://github\.com/[^\s\)]+', result.text)
        if pr_url_match:
            pr_url = pr_url_match.group()
            logger.info(f"Found PR URL via regex: {pr_url}")
        
        # Try to parse as JSON
        json_match = re.search(r'\{.*"pr_url".*\}', result.text, re.DOTALL)
        if json_match:
            try:
                result_json = json.loads(json_match.group())
                pr_url = result_json.get("pr_url") or pr_url
                branch = result_json.get("branch")
                logger.info(f"Found PR URL via JSON: {pr_url}, branch: {branch}")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON from result: {str(e)}")
        
        # Check if tool was called successfully by looking for success indicators
        if not pr_url:
            error_detail = None
            # Check if Metorial refused to call the tool
            result_lower = result.text.lower()
            refused_indicators = ["can't perform", "cannot perform", "i'm sorry", "i cannot", "unable to", "not available", "not found", "not part"]
            
            if any(indicator in result_lower for indicator in refused_indicators) or ("tool" in result_lower and ("not found" in result_lower or "not part" in result_lower)):
                error_detail = f"""Metorial is refusing to call execute_code_change tool. Common causes:
1. Deployment ID {northstar_mcp_deployment_id} is incorrect or deployment doesn't exist
2. MCP server is not deployed or not active in Metorial
3. Tool execute_code_change is not properly registered in the MCP server
4. Metorial cannot discover tools from the deployment

TROUBLESHOOTING:
- Verify NORTHSTAR_MCP_DEPLOYMENT_ID={northstar_mcp_deployment_id} matches your Metorial deployment
- Check that your MCP server (northstar_mcp_typescript) is deployed in Metorial
- Verify the deployment is active and running
- Confirm execute_code_change tool is registered in server.ts
- Try redeploying the MCP server

Metorial response: {result.text[:500]}"""
                logger.error(error_detail)
                logger.error(f"Full Metorial result: {result.text[:2000]}")
                logger.error(f"Deployment ID: {northstar_mcp_deployment_id}")
                logger.error(f"Deployments config: {deployments}")
                db_operations.update_experiment(
                    experiment_id=experiment.get("id"),
                    status="failed"
                )
            # Check if there's an error message in the result
            elif "error" in result.text.lower() or "failed" in result.text.lower():
                error_detail = f"PR creation failed. The execute_code_change tool returned an error."
                logger.error(f"{error_detail} Result: {result.text[:1000]}")
                # Update experiment status to failed
                db_operations.update_experiment(
                    experiment_id=experiment.get("id"),
                    status="failed"
                )
            else:
                error_detail = f"PR URL not found in result. The execute_code_change tool may not have been called or may have returned a response in an unexpected format."
                logger.error(f"{error_detail} Full result: {result.text[:2000]}")
                # Still update experiment status to failed
                db_operations.update_experiment(
                    experiment_id=experiment.get("id"),
                    status="failed"
                )
            
            # Always raise an error if no PR URL - don't return partial success
            raise HTTPException(
                status_code=500,
                detail=f"{error_detail or 'PR creation failed'}. Check logs for details. Metorial result (first 1000 chars): {result.text[:1000]}"
            )

        # Update experiment with PR URL (we only reach here if pr_url exists due to check above)
        db_operations.update_experiment(
            experiment_id=experiment.get("id"),
            pr_url=pr_url,
            status="running"
        )
        logger.info(f"Updated experiment {experiment.get('id')} with PR URL: {pr_url}")

        # Send Slack notification if OAuth session ID is available
        slack_notification_sent = False
        if not slack_deployment_id:
            logger.info("SLACK_DEPLOYMENT_ID not set, skipping Slack notification for experiment execution")
        elif not req.oauth_session_id:
            logger.info(f"No OAuth session ID in request for proposal {req.proposal_id}, skipping Slack notification")
        else:
            try:
                if pr_url:
                    slack_message = f"✅ Experiment executed successfully!\n"
                    slack_message += f"ID: {req.proposal_id}\n"
                    slack_message += f"Description: {req.instruction}\n"
                    slack_message += f"PR: {pr_url}"
                else:
                    slack_message = f"Experiment completed - PR creation failed\n"
                    slack_message += f"ID: {req.proposal_id}\n"
                    slack_message += f"Description: {req.instruction}"

                # Call send_slack_message with proper request object
                slack_req = SlackMessageRequest(message=slack_message, oauth_session_id=req.oauth_session_id)
                await send_slack_message(slack_req)
                slack_notification_sent = True
                logger.info(f"Successfully sent Slack notification for experiment {req.proposal_id}")
            except Exception as slack_error:
                # Don't fail the execution if Slack notification fails, but log the error
                logger.warning(f"Failed to send Slack notification for experiment execution: {str(slack_error)}")
                logger.warning(f"OAuth session ID: {req.oauth_session_id[:20]}..." if req.oauth_session_id else "No OAuth session ID")
                logger.warning(f"Slack deployment ID: {slack_deployment_id}" if slack_deployment_id else "No Slack deployment ID")
                import traceback
                logger.warning(f"Slack error traceback: {traceback.format_exc()}")

        # Create activity log
        db_operations.create_activity_log(
            message=f"Executed experiment {req.proposal_id}: {req.instruction[:50]}..." + (f" PR: {pr_url}" if pr_url else " (PR creation may have failed)"),
            proposal_id=req.proposal_id,
            experiment_id=experiment.get("id"),
            log_type="success" if pr_url else "warning"
        )

        return {
            "status": "success",
            "proposal_id": req.proposal_id,
            "experiment_id": experiment.get("id"),
            "pr_url": pr_url,
            "branch": branch,
            "slack_notification_sent": slack_notification_sent,
            "message": f"Experiment executed successfully. PR created: {pr_url}" + (f" Slack notification sent." if slack_notification_sent else f" Note: Slack notification {'skipped (no deployment ID)' if not slack_deployment_id else 'skipped (no OAuth session)' if not req.oauth_session_id else 'failed - check logs'}.")
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SlackMessageRequest(BaseModel):
    message: str
    oauth_session_id: str


class InitializeRepoRequest(BaseModel):
    repo: str  # Format: "owner/repo"
    oauth_session_id: str  # For Slack notifications


class QueryKnowledgeRequest(BaseModel):
    repo: str  # Format: "owner/repo"
    query: str


@app.post("/slack/message")
async def send_slack_message(req: SlackMessageRequest):
    """
    Send a message to Slack via Metorial.
    Used for notifications and updates.
    """
    try:
        result = await metorial.run(
            client=openai_client,
            message=f"""Post this message to Slack: "{req.message}"

Use the available Slack tools to post to any public channel.""",
            model="gpt-4o",
            server_deployments=[{
                "serverDeploymentId": slack_deployment_id,
                "oauthSessionId": req.oauth_session_id
            }],
            max_steps=10
        )

        return {
            "status": "success",
            "result": result.text
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Repository management endpoints

@app.post("/repositories")
async def connect_repository(req: ConnectRepositoryRequest):
    """
    Connect a GitHub repository to Northstar.

    This will:
    1. Validate the repository format
    2. Check if repository already exists
    3. Create or update repository record
    """
    try:
        # Check if repository already exists
        existing_repo = db_operations.get_repository(req.repo_fullname)
        
        if existing_repo:
            # Update existing repository
            repo = db_operations.update_repository(
                req.repo_fullname,
                is_active=True,
                default_branch=req.default_branch,
                base_branch=req.base_branch
            )
        else:
            # Create new repository
            repo = db_operations.create_repository(
                repo_fullname=req.repo_fullname,
                default_branch=req.default_branch,
                base_branch=req.base_branch
            )

        # Deactivate other repositories
        all_repos = db_operations.list_repositories()
        for other_repo in all_repos:
            if other_repo.get("repo_fullname") != req.repo_fullname:
                db_operations.update_repository(
                    other_repo.get("repo_fullname"),
                    is_active=False
                )

        # Create activity log
        db_operations.create_activity_log(
            message=f"Connected GitHub repository: {req.repo_fullname}",
            log_type="success"
        )

        return {
            "status": "success",
            "repository": repo,
            "message": f"Repository {req.repo_fullname} connected successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/repositories")
async def list_repositories():
    """
    List all connected repositories.
    """
    try:
        repos = db_operations.list_repositories()
        return {
            "status": "success",
            "repositories": repos,
            "count": len(repos)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/debug/mcp-deployment")
async def debug_mcp_deployment():
    """
    Debug endpoint to test MCP deployment and list available tools.
    """
    try:
        if not northstar_mcp_deployment_id:
            return {
                "status": "error",
                "message": "NORTHSTAR_MCP_DEPLOYMENT_ID is not set",
                "deployment_id": None
            }
        
        # Try to list tools from the deployment
        deployments = [{"serverDeploymentId": northstar_mcp_deployment_id}]
        
        logger.info(f"Testing MCP deployment: {northstar_mcp_deployment_id}")
        
        result = await metorial.run(
            client=openai_client,
            message="List all available tools from the deployment. What tools can you access?",
            model="gpt-4o",
            server_deployments=deployments,
            max_steps=5
        )
        
        return {
            "status": "success",
            "deployment_id": northstar_mcp_deployment_id,
            "metorial_response": result.text[:1000],
            "full_response": result.text
        }
    except Exception as e:
        logger.error(f"Error testing MCP deployment: {str(e)}")
        import traceback
        return {
            "status": "error",
            "deployment_id": northstar_mcp_deployment_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.get("/repositories/active")
async def get_active_repository():
    """
    Get the currently active repository.
    
    Returns 404 if no active repository, 200 with repository if found.
    """
    try:
        repo = db_operations.get_active_repository()
        if not repo:
            raise HTTPException(status_code=404, detail="No active repository found")
        return {
            "status": "success",
            "repository": repo
        }
    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e).lower()
        # If table doesn't exist, return 404 instead of 500
        if "relation" in error_str or "table" in error_str or "does not exist" in error_str:
            raise HTTPException(
                status_code=404, 
                detail="No active repository found. Please create the repositories table in Supabase first."
            )
        raise HTTPException(status_code=500, detail=str(e))


# GET endpoints for retrieving data from Supabase

@app.get("/proposals")
async def get_proposals(status: Optional[str] = None, limit: int = 50, repo_id: Optional[str] = None):
    """
    Get list of proposals, optionally filtered by status or repository.

    Query params:
    - status: Optional filter (pending, approved, rejected, executing, completed)
    - limit: Maximum number of proposals to return (default: 50)
    - repo_id: Optional repository ID filter
    """
    try:
        proposals = db_operations.list_proposals(limit=limit, status=status, repo_id=repo_id)
        return {
            "status": "success",
            "proposals": proposals,
            "count": len(proposals)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/proposals/{proposal_id}")
async def get_proposal(proposal_id: str):
    """
    Get a specific proposal by ID.
    """
    try:
        proposal = db_operations.get_proposal(proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
        return {
            "status": "success",
            "proposal": proposal
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/experiments")
async def get_experiments(status: Optional[str] = None, limit: int = 50):
    """
    Get list of experiments, optionally filtered by status.

    Query params:
    - status: Optional filter (running, completed, failed, cancelled)
    - limit: Maximum number of experiments to return (default: 50)
    """
    try:
        experiments = db_operations.list_experiments(limit=limit, status=status)
        return {
            "status": "success",
            "experiments": experiments,
            "count": len(experiments)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/experiments/{experiment_id}")
async def get_experiment(experiment_id: str):
    """
    Get a specific experiment by ID.
    """
    try:
        experiment = db_operations.get_experiment(experiment_id)
        if not experiment:
            raise HTTPException(status_code=404, detail=f"Experiment {experiment_id} not found")
        return {
            "status": "success",
            "experiment": experiment
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/experiments/by-proposal/{proposal_id}")
async def get_experiment_by_proposal(proposal_id: str):
    """
    Get experiment associated with a proposal ID.
    
    Returns 404 if no experiment exists (which is normal for pending proposals).
    """
    try:
        experiment = db_operations.get_experiment_by_proposal(proposal_id)
        if not experiment:
            # Return 404 - this is expected for proposals that haven't been approved yet
            raise HTTPException(
                status_code=404,
                detail=f"Experiment for proposal {proposal_id} not found. Experiments are only created when proposals are approved."
            )
        return {
            "status": "success",
            "experiment": experiment
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/activity-logs")
async def get_activity_logs(limit: int = 50):
    """
    Get recent activity logs.

    Query params:
    - limit: Maximum number of logs to return (default: 50)
    """
    try:
        logs = db_operations.list_activity_logs(limit=limit)
        return {
            "status": "success",
            "logs": logs,
            "count": len(logs)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Proposal approval endpoint

@app.post("/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: str,
    req: ApproveProposalRequest
):
    """
    Approve a proposal and execute it.

    This will:
    1. Update proposal status to 'approved'
    2. Save the update_block to the proposal
    3. Create an experiment record
    4. Execute the experiment (create PR)
    """
    try:
        # Ensure proposal_id matches
        if req.proposal_id != proposal_id:
            raise HTTPException(
                status_code=400,
                detail="Proposal ID in path must match proposal ID in request body"
            )

        # Get proposal
        proposal = db_operations.get_proposal(proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")

        # Update proposal with update_block and status
        proposal = db_operations.update_proposal(
            proposal_id=proposal_id,
            status="approved",
            update_block=req.update_block
        )

        # Get active repository
        active_repo = db_operations.get_active_repository()
        if not active_repo:
            raise HTTPException(
                status_code=400,
                detail="No active repository connected. Please connect a repository first."
            )

        # Extract file path from technical_plan
        file_path = None
        technical_plan = proposal.get("technical_plan", [])
        if technical_plan and len(technical_plan) > 0:
            file_path = technical_plan[0].get("file")

        if not file_path:
            raise HTTPException(
                status_code=400,
                detail="No file path found in proposal's technical plan. Cannot execute experiment."
            )

        # Get OAuth session ID from proposal
        oauth_session_id = proposal.get("oauth_session_id") or ""

        # Create experiment execution request with repo and file info
        execute_req = ExecuteExperimentRequest(
            proposal_id=proposal_id,
            instruction=proposal.get("idea_summary", ""),
            update_block=req.update_block,
            oauth_session_id=oauth_session_id,
            repo_fullname=active_repo.get("repo_fullname"),
            file_path=file_path,
            base_branch=active_repo.get("base_branch") or active_repo.get("default_branch") or "main"
        )

        # Send Slack notification about approval
        import logging
        logger = logging.getLogger(__name__)
        
        if not slack_deployment_id:
            logger.info("SLACK_DEPLOYMENT_ID not set, skipping Slack notification for approval")
        elif not oauth_session_id:
            logger.info(f"No OAuth session ID in proposal {proposal_id}, skipping Slack notification for approval")
        else:
            try:
                slack_message = f"Experiment approved and executing\n"
                slack_message += f"Proposal ID: {proposal_id}\n"
                slack_message += f"Description: {proposal.get('idea_summary', 'Unknown')}"
                
                # Call send_slack_message with proper request object
                slack_req = SlackMessageRequest(message=slack_message, oauth_session_id=oauth_session_id)
                await send_slack_message(slack_req)
                logger.info(f"Successfully sent Slack notification for approval of proposal {proposal_id}")
            except Exception as slack_error:
                logger.warning(f"Failed to send Slack notification for approval: {str(slack_error)}")
                logger.warning(f"OAuth session ID: {oauth_session_id[:20]}..." if oauth_session_id else "No OAuth session ID")
                logger.warning(f"Slack deployment ID: {slack_deployment_id}" if slack_deployment_id else "No Slack deployment ID")

        # Execute the experiment
        try:
            execution_result = await execute_experiment(execute_req)
            
            # Create activity log with PR URL if available
            pr_url = execution_result.get("pr_url")
            log_message = f"Approved and executed proposal {proposal_id}"
            if pr_url:
                log_message += f" - PR: {pr_url}"
            else:
                log_message += " (PR creation failed - check logs)"
            
            db_operations.create_activity_log(
                message=log_message,
                proposal_id=proposal_id,
                log_type="success" if pr_url else "warning"
            )

            return {
                "status": "success",
                "proposal": proposal,
                "execution": execution_result,
                "message": execution_result.get("message", "Experiment executed")
            }
        except HTTPException as exec_error:
            # Log the execution error
            logger.error(f"Execution failed for proposal {proposal_id}: {exec_error.detail}")
            db_operations.create_activity_log(
                message=f"Failed to execute proposal {proposal_id}: {exec_error.detail[:200]}",
                proposal_id=proposal_id,
                log_type="error"
            )
            # Re-raise to return proper error to user
            raise HTTPException(
                status_code=exec_error.status_code,
                detail=f"Failed to execute experiment: {exec_error.detail}. Check backend logs for full details."
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in approve_proposal: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}. Check backend logs for details.")


@app.post("/proposals/{proposal_id}/reject")
async def reject_proposal(proposal_id: str):
    """
    Reject a proposal.

    This will update the proposal status to 'rejected'.
    """
    try:
        proposal = db_operations.update_proposal_status(proposal_id, "rejected")

        # Create activity log
        db_operations.create_activity_log(
            message=f"Rejected proposal {proposal_id}",
            proposal_id=proposal_id,
            log_type="info"
        )

        return {
            "status": "success",
            "proposal": proposal
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Knowledge base endpoints

@app.post("/northstar/initialize-repo")
async def initialize_repo(req: InitializeRepoRequest, background_tasks: BackgroundTasks):
    """
    Initialize a repository in the knowledge base.

    This endpoint:
    1. Clones the repository locally
    2. Reads and analyzes actual files
    3. Creates a Captain database
    4. Indexes files into Captain
    5. Posts detailed analysis to Slack
    """
    if not captain:
        raise HTTPException(
            status_code=503,
            detail="Captain not configured - set CAPTAIN_API_KEY and CAPTAIN_ORGANIZATION_ID"
        )

    database_name = req.repo.replace("/", "_").replace("-", "_")
    repo_path = None

    try:
        # 1. Clone the repository
        github_token = os.getenv("GITHUB_TOKEN")
        if github_token:
            repo_url = f"https://{github_token}@github.com/{req.repo}.git"
        else:
            repo_url = f"https://github.com/{req.repo}.git"

        temp_dir = Path(tempfile.mkdtemp())
        repo_path = temp_dir / "repo"

        clone_repository(repo_url, repo_path)

        # 2. Read key files for analysis
        key_files_content = read_key_files(repo_path)

        # 3. Analyze repository structure
        repo_structure = analyze_repository_structure(repo_path)

        # 4. Get indexable files
        indexable_files = get_indexable_files(repo_path)

        # 5. Read ALL indexable files for comprehensive analysis
        all_file_contents = {}

        # Start with key files
        all_file_contents.update(key_files_content)

        # Read all source code and other indexable files
        for file_path in indexable_files:
            try:
                relative_path = str(file_path.relative_to(repo_path))
                # Skip if already read as a key file
                if relative_path not in all_file_contents:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    # Limit individual file size to avoid overwhelming the context
                    all_file_contents[relative_path] = content[:10000]  # First 10k chars per file
            except Exception as e:
                print(f"Failed to read {file_path}: {e}")
                continue

        # 6. Build comprehensive context for AI analysis
        context = f"""
Repository: {req.repo}

=== REPOSITORY STRUCTURE ===
Total Files: {repo_structure['total_files']}
Languages Detected: {', '.join(repo_structure['languages_detected'])}
Directories: {len(repo_structure['directories'])}

File Types:
{chr(10).join(f"  {ext}: {count}" for ext, count in sorted(repo_structure['file_counts_by_type'].items(), key=lambda x: -x[1])[:10])}

=== ALL FILE CONTENTS ({len(all_file_contents)} files) ===
"""

        # Add ALL file contents to context
        for filename, content in sorted(all_file_contents.items()):
            context += f"\n{'='*60}\n"
            context += f"FILE: {filename} ({len(content)} chars)\n"
            context += f"{'='*60}\n"
            context += content
            if len(content) >= 10000:
                context += "\n\n... (truncated at 10,000 characters)"
            context += "\n"

        # 7. Have AI analyze ALL file contents
        result = await metorial.run(
            client=openai_client,
            message=f"""
Analyze this repository thoroughly based on ACTUAL file contents from ALL files:

{context}

You have access to the complete contents of ALL {len(all_file_contents)} files in this repository.

Provide a comprehensive analysis:
1. Product Overview: What does this product actually do? (based on README and actual code)
2. Architecture: What architectural patterns are used? (based on actual file structure, imports, and code organization)
3. Tech Stack: What frameworks, libraries, and tools are used? (based on actual dependencies and code)
4. Code Structure: Describe the actual functions, classes, and modules you see
5. Key Features: What specific features are implemented? (reference actual code)
6. Development Setup: How would a developer get started?

Then post this analysis to Slack in a well-formatted message starting with:
"📚 Knowledge Base Initialized: {req.repo}"

IMPORTANT:
- You have READ ALL {len(all_file_contents)} files - reference specific code, functions, and implementations
- Be specific and factual - cite actual file names, function names, and code snippets
- DO NOT use phrases like "likely includes" or "probably uses"
- Only state facts from the actual files you've read
            """,
            model="gpt-4o",
            server_deployments=[{
                "serverDeploymentId": slack_deployment_id,
                "oauthSessionId": req.oauth_session_id
            }],
            max_steps=10
        )

        # 8. Create Captain database
        try:
            captain.create_database(database_name)
        except Exception as e:
            if "already exists" not in str(e).lower():
                raise

        # 9. Index files into Captain in background
        async def index_files_background():
            try:
                for file_path in indexable_files[:100]:  # Limit to 100 files for MVP
                    try:
                        file_content = file_path.read_bytes()
                        file_info = prepare_file_for_captain(file_path, repo_path)

                        captain.upload_file(
                            database_name=database_name,
                            file_path=file_info['path'],
                            file_content=file_content,
                            metadata=file_info
                        )
                    except Exception as e:
                        print(f"Failed to index {file_path}: {e}")
                        continue
            finally:
                # Cleanup temp directory
                if repo_path and repo_path.exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)

        background_tasks.add_task(index_files_background)

        return {
            "status": "success",
            "database_name": database_name,
            "analysis": result.text,
            "stats": {
                "total_files": repo_structure['total_files'],
                "files_read_and_analyzed": len(all_file_contents),
                "indexable_files": len(indexable_files),
                "languages": repo_structure['languages_detected'],
                "files_analyzed": list(all_file_contents.keys())
            },
            "message": f"Repository analyzed - read {len(all_file_contents)} files, indexing {len(indexable_files)} files in background"
        }

    except Exception as e:
        # Cleanup on error
        if repo_path and repo_path.exists():
            shutil.rmtree(repo_path.parent, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/northstar/query-knowledge")
async def query_knowledge(req: QueryKnowledgeRequest):
    """
    Query the knowledge base for a specific repository.

    Returns context-aware answers about the codebase, architecture, and product.
    """
    if not captain:
        raise HTTPException(
            status_code=503,
            detail="Captain not configured"
        )

    try:
        database_name = req.repo.replace("/", "_").replace("-", "_")

        # Query Captain database
        result = captain.query(
            database_name=database_name,
            query=req.query,
            include_files=True
        )

        return {
            "status": "success",
            "answer": result.get("response"),
            "relevant_files": result.get("relevant_files", []),
            "database_name": database_name
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/northstar/knowledge-status")
async def knowledge_status(repo: str):
    """
    Check if a repository has been initialized in the knowledge base.
    """
    if not captain:
        raise HTTPException(
            status_code=503,
            detail="Captain not configured"
        )

    try:
        databases = captain.list_databases()
        database_name = repo.replace("/", "_").replace("-", "_")

        repo_db = next(
            (db for db in databases if db["database_name"] == database_name),
            None
        )

        if not repo_db:
            return {
                "initialized": False,
                "database_name": database_name
            }

        # Get file count
        files = captain.list_files(database_name, limit=1)

        return {
            "initialized": True,
            "database_name": database_name,
            "database_info": repo_db,
            "has_files": len(files) > 0
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def run_autonomous_agent(
    user_message: str,
    channel: str,
    user_id: str,
    context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Unified autonomous agent that reasons and acts.

    This is the core agent function that:
    1. Receives user input (from Slack or other interfaces)
    2. Uses Metorial to orchestrate GPT-4o with all MCP tools
    3. Lets GPT-4o reason autonomously about what to do
    4. Executes tools as needed (code changes, GitHub ops, Slack replies)
    5. Returns results

    Args:
        user_message: The user's request/message
        channel: Slack channel ID (for posting responses)
        user_id: Slack user ID
        context: Optional context (repo info, etc.)

    Returns:
        Agent's response text
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Get active repository context
        active_repo = db_operations.get_active_repository()
        repo_fullname = active_repo.get("repo_fullname") if active_repo else "No repository connected"
        base_branch = active_repo.get("base_branch", "main") if active_repo else "main"

        logger.info(f"Running autonomous agent for user {user_id} in channel {channel}")
        logger.info(f"User message: {user_message}")
        logger.info(f"Active repo: {repo_fullname}")

        # STAGE 1: Quick triage - determine what tools are needed
        logger.info("🧠 Stage 1: Analyzing request to determine required tools...")

        # Use OpenAI directly for triage (faster, no deployments needed)
        triage_response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": f"""Analyze this user request and determine what tools/actions are needed.

User request: "{user_message}"
Active repository: {repo_fullname}

Classify the request as ONE of these types and respond with ONLY the type name:

1. "CASUAL_CHAT" - Greetings, small talk, "hey", "what's up", "how are you", general questions not about code
2. "REPO_ANALYSIS" - Questions about the repo: "what does this repo do", "tell me about the code", "how does X work"
3. "ANALYTICS_QUERY" - Questions about analytics, metrics, DAUs, MAUs, events, retention, user behavior: "how are our DAUs", "show me user retention", "what's our conversion rate", "how many signups", "most popular features"
4. "CODE_CHANGE" - Requests to modify code: "make a pr", "change X to Y", "add feature Z", "update the button color"
5. "EXPERIMENT_PROPOSAL" - "propose an experiment", "suggest improvements"

Respond with ONLY ONE WORD - the type name in ALL CAPS."""
            }],
            max_tokens=10
        )

        request_type = triage_response.choices[0].message.content.strip().upper()
        logger.info(f"📊 Request classified as: {request_type}")

        # STAGE 2: Execute with appropriate deployments
        if request_type == "CASUAL_CHAT":
            # Simple chat - only needs Slack
            logger.info("💬 Handling as casual chat (Slack only)")
            deployments = [{
                "serverDeploymentId": slack_deployment_id,
                "oauthSessionId": slack_oauth_session_id
            }]
            prompt = f"""User said: "{user_message}"

Post a casual, conversational reply to Slack channel {channel}.

Personality: Sound like a calm, capable product engineer. Keep it short and natural.
- Short sentences (max 12-14 words)
- Use natural transitions like "Hey." "Got it." "Sounds good."
- No emojis, no exclamation marks, no buzzwords
- Treat them like a teammate, not a user

Use the Slack chat.postMessage tool to post your reply to channel {channel}."""
            max_steps = 3

        elif request_type == "REPO_ANALYSIS":
            # Use Captain knowledge base to answer questions about the repo
            logger.info("📚 Handling as repo analysis (Captain + Slack)")

            # Query Captain for repo information
            # Extract the actual question from the user message
            query = user_message.lower()
            query = query.replace("*", "").strip()
            query = query.replace("_", "").strip()
            query = query.replace("northstar", "").strip()

            # Remove common phrases
            for phrase in ["tell me about", "what is", "what's", "describe", "explain"]:
                query = query.replace(phrase, "").strip()

            # If query is too generic or empty, use default
            if not query or query in ["this repo", "the repo", "repo", "this", "is repo"]:
                query = "What does this repository do? Describe the project, its purpose, and key features."

            logger.info(f"User query: {query}")
            logger.info(f"📥 Analyzing repo: {repo_fullname}")

            # Clone repo and read important files directly
            import tempfile
            import shutil
            from pathlib import Path
            repo_path = None
            response_text = ""

            try:
                # Clone repository to temp directory
                temp_dir = tempfile.mkdtemp(prefix=f"northstar_analysis_")
                repo_path = Path(temp_dir)
                clone_repository(f"https://github.com/{repo_fullname}.git", repo_path)
                logger.info(f"Cloned repo to {repo_path}")

                # Identify important files to read
                important_files = []

                # 1. Always read README
                readme_files = list(repo_path.glob("README*"))
                for readme in readme_files[:1]:  # Take first README
                    try:
                        content = readme.read_text(encoding='utf-8', errors='ignore')
                        important_files.append(f"=== {readme.name} ===\n{content[:3000]}")
                        logger.info(f"Read {readme.name} ({len(content)} chars)")
                    except Exception as e:
                        logger.warning(f"Failed to read {readme.name}: {e}")

                # 2. Read package.json or requirements.txt to understand dependencies
                package_json = repo_path / "package.json"
                if package_json.exists():
                    try:
                        content = package_json.read_text(encoding='utf-8', errors='ignore')
                        important_files.append(f"=== package.json ===\n{content}")
                        logger.info(f"Read package.json")
                    except Exception as e:
                        logger.warning(f"Failed to read package.json: {e}")

                requirements = repo_path / "requirements.txt"
                if requirements.exists():
                    try:
                        content = requirements.read_text(encoding='utf-8', errors='ignore')
                        important_files.append(f"=== requirements.txt ===\n{content}")
                        logger.info(f"Read requirements.txt")
                    except Exception as e:
                        logger.warning(f"Failed to read requirements.txt: {e}")

                # 3. Get directory structure
                structure_lines = []
                for item in sorted(repo_path.rglob("*")):
                    if ".git" in str(item) or "node_modules" in str(item) or "__pycache__" in str(item):
                        continue
                    rel_path = item.relative_to(repo_path)
                    depth = len(rel_path.parts) - 1
                    indent = "  " * depth
                    if item.is_file():
                        structure_lines.append(f"{indent}{item.name}")
                    elif item.is_dir() and depth < 3:  # Only show up to 3 levels deep
                        structure_lines.append(f"{indent}{item.name}/")
                    if len(structure_lines) >= 100:  # Limit structure size
                        break

                structure = "\n".join(structure_lines[:100])
                important_files.append(f"=== Repository Structure ===\n{structure}")
                logger.info(f"Generated directory structure")

                # 4. Read main entry point files
                entry_points = [
                    "index.js", "index.ts", "main.py", "app.py", "main.jsx", "App.jsx",
                    "index.html", "main.go", "index.php"
                ]
                for entry in entry_points:
                    entry_file = repo_path / "src" / entry if (repo_path / "src").exists() else repo_path / entry
                    if entry_file.exists():
                        try:
                            content = entry_file.read_text(encoding='utf-8', errors='ignore')
                            important_files.append(f"=== {entry} ===\n{content[:2000]}")
                            logger.info(f"Read {entry}")
                            break  # Only read first found entry point
                        except Exception as e:
                            logger.warning(f"Failed to read {entry}: {e}")

                # Combine all context
                full_context = "\n\n".join(important_files)
                logger.info(f"Built context from {len(important_files)} files ({len(full_context)} total chars)")

                # Query OpenAI with Captain's infinite context API
                from openai import OpenAI

                captain_client = OpenAI(
                    base_url="https://api.runcaptain.com/v1",
                    api_key=os.getenv("CAPTAIN_API_KEY"),
                    default_headers={
                        "X-Organization-ID": os.getenv("CAPTAIN_ORGANIZATION_ID")
                    }
                )

                gpt_response = captain_client.chat.completions.create(
                    model="captain-voyager-latest",
                    messages=[
                        {
                            "role": "system",
                            "content": f"You are analyzing the GitHub repository {repo_fullname} for a product manager audience. Focus on what the product does, its purpose, and user-facing features rather than technical implementation details. Provide specific, factual answers based ONLY on the repository files and content provided. Never say 'likely', never guess, and never ask clarifying questions. Answer directly and concisely in product language."
                        },
                        {
                            "role": "user",
                            "content": f"{query}\n\nProvide a direct, product-focused answer in 2-3 sentences. Emphasize what users can do with this product and its main value proposition."
                        }
                    ],
                    extra_body={
                        "captain": {
                            "context": full_context
                        }
                    },
                    max_tokens=200
                )

                response_text = gpt_response.choices[0].message.content.strip()
                logger.info(f"✅ Captain infinite context response: {response_text[:200]}...")

            except Exception as e:
                logger.error(f"Repo analysis failed: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                response_text = f"I encountered an error while analyzing {repo_fullname}: {str(e)}"

            finally:
                # Cleanup cloned repo
                if repo_path and os.path.exists(str(repo_path)):
                    shutil.rmtree(str(repo_path))
                    logger.info(f"Cleaned up {repo_path}")

            # Now use Slack deployment to post the response
            deployments = [
                {"serverDeploymentId": slack_deployment_id, "oauthSessionId": slack_oauth_session_id}
            ]
            prompt = f"""Post this message to Slack channel {channel}:

"{response_text}"

Personality: Sound like a calm, capable product engineer.
- Short sentences (max 12-14 words)
- No emojis, no exclamation marks
- Treat them like a teammate

Use the Slack chat.postMessage tool."""
            max_steps = 3

        elif request_type == "ANALYTICS_QUERY":
            # Analytics query - needs PostHog + Slack
            logger.info("📊 Handling as analytics query (PostHog + Slack)")

            if not posthog_deployment_id:
                logger.warning("PostHog deployment ID not configured")
                response_text = "Analytics integration is not configured yet. Please set up PostHog to view metrics."
                deployments = [
                    {"serverDeploymentId": slack_deployment_id, "oauthSessionId": slack_oauth_session_id}
                ]
                prompt = f"""Post this message to Slack channel {channel}:

"{response_text}"

Use the Slack chat.postMessage tool."""
                max_steps = 3
            else:
                # Use PostHog MCP to query analytics
                deployments = [
                    {"serverDeploymentId": posthog_deployment_id},
                    {"serverDeploymentId": slack_deployment_id, "oauthSessionId": slack_oauth_session_id}
                ]
                prompt = f"""User is asking about analytics: "{user_message}"

Your task:
1. First, check if PostHog is properly configured by listing available tools or querying for project info.

2. If PostHog has access to data:
   - Query the relevant metrics (DAUs/MAUs, retention, events, conversions, feature usage)
   - Interpret results in a product-focused way with trends and insights
   - Post to Slack channel {channel} using chat.postMessage

   Format the Slack message with this structure:
   *Analytics Report*

   *Metric:* [metric name]
   *Current:* [value]
   *Trend:* [up/down X% from previous period]

   *Key insights:*
   [2-3 bullet points with context and interpretation]

   Personality: Sound like a calm, capable product engineer.
   - Short sentences (max 12-14 words)
   - Add brief analytical reflection on what the data means
   - Use natural language like "Looks good." "This is promising."
   - No emojis, no exclamation marks

3. If PostHog is NOT configured or has no data access:
   - Post a helpful message to Slack channel {channel} using chat.postMessage
   - Format: "PostHog isn't connected yet. Need to configure the MCP server with your API key and project ID."
   - Keep it brief and practical

IMPORTANT: Always end by posting to Slack, whether you have data or not."""
                max_steps = 15

        elif request_type == "CODE_CHANGE":
            # Needs all tools: GitHub + Northstar + Slack
            logger.info("🔧 Handling as code change (GitHub + Northstar + Slack)")
            deployments = [
                {"serverDeploymentId": slack_deployment_id, "oauthSessionId": slack_oauth_session_id},
                {"serverDeploymentId": github_deployment_id},
                {"serverDeploymentId": northstar_mcp_deployment_id}
            ]
            prompt = f"""User request: "{user_message}"
Repository: {repo_fullname}
Base branch: {base_branch}

1. Use GitHub tools to browse the repo and find relevant files
2. Analyze the code to understand what needs to change
3. Generate a code diff (update_block with +/- markers)
4. Call the execute_code_change tool with:
   - instruction: Clear description
   - update_block: Code diff with +/- markers
   - repo: "{repo_fullname}"
   - file_path: The file you identified
   - base_branch: "{base_branch}"
5. Post the PR URL to Slack channel {channel} using Slack chat.postMessage

Format the Slack message with this structure:
*Code change executed*

*PR:* [PR URL as clickable link]
*Files changed:* [number] file(s)
*Changes:* [one-line summary]

Personality: Sound like a calm, capable product engineer.
- Start with a crisp confirmation: "On it." or "All done."
- Add a brief reflection on the change (max 12-14 words)
- Use natural transitions like "Looks good." "This should help."
- No emojis, no exclamation marks

Use Slack markdown: *bold* for labels, clean structure."""
            max_steps = 25

        else:  # EXPERIMENT_PROPOSAL or unknown
            # Needs GitHub + Northstar + Slack
            logger.info("🧪 Handling as experiment proposal (GitHub + Northstar + Slack)")
            deployments = [
                {"serverDeploymentId": slack_deployment_id, "oauthSessionId": slack_oauth_session_id},
                {"serverDeploymentId": github_deployment_id},
                {"serverDeploymentId": northstar_mcp_deployment_id}
            ]
            prompt = f"""User request: "{user_message}"
Repository: {repo_fullname}

1. Use GitHub tools to fetch codebase context
2. Call propose_experiment tool with the codebase context
3. Format the proposal with rich Slack markdown and post to channel {channel}

Use this exact format for the Slack message:

*New experiment proposed:*
[Idea summary - one line description]

*Category:* [category]
*Confidence:* [confidence as percentage]%
*Expected impact:* [delta_pct as percentage with sign]% [metric]
*PR Ready:* [True/False]

*Rationale:*
[Detailed explanation of the problem and proposed solution]

*Technical Plan:*
• [file 1]: [action]
• [file 2]: [action]

Personality: Sound like a calm, capable product engineer.
- Keep rationale clear and analytical (2-3 sentences max)
- Add brief reflection on why this matters
- Use natural language like "This should improve..." "Looks promising."
- Short sentences (max 12-14 words)
- No emojis, no exclamation marks

Use Slack markdown formatting:
- *bold* for labels
- Single line breaks between sections
- Bullet points (•) for lists
- Keep it clean and scannable"""
            max_steps = 20

        logger.info(f"🚀 Stage 2: Executing with {len(deployments)} deployment(s), max_steps={max_steps}")

        # Execute the actual task
        result = await metorial.run(
            client=openai_client,
            message=prompt,
            model="gpt-4o",
            server_deployments=deployments,
            max_steps=max_steps
        )

        logger.info(f"✅ Agent execution complete. Result: {result.text[:500]}...")

        return result.text

    except Exception as e:
        logger.error(f"Error in autonomous agent: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

        # Try to post error to Slack
        try:
            if slack_deployment_id and slack_oauth_session_id:
                error_result = await metorial.run(
                    client=openai_client,
                    message=f'Post this message to Slack channel {channel}: "Sorry, I encountered an error: {str(e)[:200]}"',
                    model="gpt-4o",
                    server_deployments=[{
                        "serverDeploymentId": slack_deployment_id,
                        "oauthSessionId": slack_oauth_session_id
                    }],
                    max_steps=2
                )
        except Exception as slack_error:
            logger.error(f"Failed to post error to Slack: {str(slack_error)}")

        return f"Error: {str(e)}"


@app.post("/test-agent")
async def test_agent():
    """Test endpoint to verify the agent works."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Test agent endpoint called")

    # Test with a simple message
    result = await run_autonomous_agent(
        user_message="hey northstar",
        channel="test-channel",
        user_id="test-user"
    )

    return {"status": "success", "result": result}


@app.post("/test-slack-post")
async def test_slack_post(channel: str = "C09QL9V1J1F"):
    """Test endpoint to directly post to Slack using Metorial."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Testing Slack post to channel {channel}")

    try:
        result = await metorial.run(
            client=openai_client,
            message=f'Use the Slack post_message tool to post "Test message from Northstar backend" to channel {channel}',
            model="gpt-4o",
            server_deployments=[{
                "serverDeploymentId": slack_deployment_id,
                "oauthSessionId": slack_oauth_session_id
            }],
            max_steps=3
        )

        logger.info(f"Slack post result: {result.text}")
        return {"status": "success", "result": result.text}
    except Exception as e:
        logger.error(f"Error posting to Slack: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {"status": "error", "error": str(e)}


@app.post("/slack/events")
async def slack_events(request: Request):
    """
    Slack Events API webhook.

    Receives events when:
    - Messages mention "northstar"
    - Direct messages to the bot
    - App mentions (@northstar)

    Routes to the autonomous agent for reasoning and execution.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        body = await request.json()
        logger.info(f"📨 Received Slack event: {body.get('type')}")

        # Handle URL verification challenge
        if body.get("type") == "url_verification":
            logger.info("URL verification challenge received")
            return {"challenge": body.get("challenge")}

        # Handle app_mention or message events
        event = body.get("event", {})
        event_type = event.get("type")
        logger.info(f"Event type: {event_type}")

        # Ignore bot messages to prevent loops
        if event.get("bot_id"):
            logger.info(f"Ignoring bot message (bot_id: {event.get('bot_id')})")
            return {"ok": True}

        if event.get("subtype") == "bot_message":
            logger.info("Ignoring bot message (subtype: bot_message)")
            return {"ok": True}

        # Check if message mentions "northstar" (case-insensitive)
        text = event.get("text", "")
        text_lower = text.lower()
        logger.info(f"Message text: '{text}' (searching for 'northstar')")

        if "northstar" not in text_lower:
            logger.info("Message doesn't mention 'northstar', ignoring")
            return {"ok": True}

        # Extract channel and original message
        channel = event.get("channel")
        user_message = event.get("text", "")
        user_id = event.get("user")

        logger.info(f"✅ Northstar mentioned by user {user_id} in channel {channel}: {user_message}")
        logger.info(f"🚀 Starting autonomous agent in background...")

        # Run the autonomous agent (non-blocking)
        # Note: We return immediately to Slack, agent runs in background
        import asyncio
        asyncio.create_task(run_autonomous_agent(
            user_message=user_message,
            channel=channel,
            user_id=user_id
        ))

        logger.info("✓ Agent task created, returning OK to Slack")
        return {"ok": True}

    except Exception as e:
        logger.error(f"Error handling Slack event: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/slack/commands")
async def slack_commands(request: Request):
    """
    Slack slash commands webhook.

    Handles commands like:
    - /northstar help
    - /northstar propose experiment
    - /northstar status

    Routes to the autonomous agent for reasoning and execution.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        form_data = await request.form()

        command = form_data.get("command")
        text = form_data.get("text", "")
        user_id = form_data.get("user_id")
        channel_id = form_data.get("channel_id")

        logger.info(f"Slash command {command} from user {user_id}: {text}")

        # Respond immediately (Slack requires response within 3 seconds)
        response = {
            "response_type": "in_channel",
            "text": f"Processing your request: {text}"
        }

        # Run the autonomous agent (non-blocking)
        import asyncio
        asyncio.create_task(run_autonomous_agent(
            user_message=text,
            channel=channel_id,
            user_id=user_id
        ))

        return response

    except Exception as e:
        logger.error(f"Error handling slash command: {str(e)}")
        return {
            "response_type": "ephemeral",
            "text": f"Error processing command: {str(e)}"
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
