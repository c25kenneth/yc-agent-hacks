"""Northstar FastAPI Orchestrator - AI-powered experimentation platform."""

from fastapi import FastAPI, HTTPException, BackgroundTasks
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

load_dotenv()

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
northstar_mcp_deployment_id = os.getenv("NORTHSTAR_MCP_DEPLOYMENT_ID")  # Will set after deploying

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
        
        try:
            if northstar_mcp_deployment_id:
                # Try to use propose_experiment tool
                result = await metorial.run(
                    client=openai_client,
                    message=f"""
                    Use the propose_experiment tool to generate an experiment proposal.
                    
                    Repository context:
                    {repo_context}
                    
                    Return the proposal as JSON with the following format:
                    {{
                        "proposal_id": "exp-001",
                        "idea_summary": "Brief summary",
                        "rationale": "Reasoning behind the proposal",
                        "expected_impact": {{"metric": "conversion_rate", "delta_pct": 0.05}},
                        "technical_plan": [{{"file": "path/to/file", "action": "description"}}],
                        "category": "category_name",
                        "confidence": 0.8
                    }}
                    """,
                    model="gpt-4o",
                    server_deployments=deployments,
                    max_steps=5
                )
            else:
                raise Exception("MCP tool not available")
        except Exception as mcp_error:
            # Fallback: Generate proposal directly using GPT-4o with repository context
            result = await metorial.run(
                client=openai_client,
                message=f"""
                YOU ARE A UI/VISUAL DESIGN-FOCUSED CODE ANALYST. Your PRIMARY focus is identifying VISUAL DESIGN AND USER INTERFACE PROBLEMS in the actual code and proposing MEASURABLE UI/VISUAL IMPROVEMENTS. Prioritize UI improvements over UX improvements (focus on what users SEE, not just what they experience).
                
                REPOSITORY CONTEXT (ACTUAL CODE FROM {repo_fullname}):
                {repo_context}
                
                CRITICAL INSTRUCTIONS:
                1. IGNORE configuration files (package.json, pubspec.yaml, tsconfig.json, etc.) - these are NOT user-written code
                2. FOCUS ONLY on user-written source code files (Dart, JavaScript, TypeScript, Python, etc.)
                3. ANALYZE ACTUAL USER EXPERIENCE FLOWS and identify REAL UX/UI PROBLEMS:
                   
                   UX PROBLEMS (User Experience):
                   - Missing error handling that causes poor UX (crashes, unhelpful errors)
                   - Missing loading states (users see nothing while waiting)
                   - Poor user feedback (no success/error messages)
                   - Confusing navigation flows
                   - Slow/unresponsive UI (performance issues affecting UX)
                   - Accessibility issues (missing labels, poor contrast)
                   - Form validation issues
                   - Missing empty states
                   - Poor error messages
                   - Unclear user flows
                   
                   UI PROBLEMS (User Interface / Visual Design) - PRIORITIZE THESE:
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
                
                Step 1: UNDERSTAND THE USER FLOW
                - Map out actual user flows from the code (e.g., "User opens app → sees loading → authenticates → sees home")
                - Identify each step in the flow and what could go wrong
                - Look for places where users might get confused, stuck, or see errors
                
                Step 2: IDENTIFY SPECIFIC UX/UI PROBLEMS IN THE CODE
                - Find actual code that handles user interactions (buttons, forms, navigation, API calls)
                - Look for missing error handling: try/catch blocks, error states, error messages
                - Find missing loading states: async operations without loading indicators
                - Identify poor user feedback: no success messages, unclear error messages
                - Spot performance issues: blocking operations, missing debouncing, inefficient renders
                - Check for accessibility: missing labels, poor keyboard navigation
                - Analyze UI code: component styling, layouts, visual hierarchy, colors, spacing
                - Find inconsistent styling: same elements styled differently across the app
                - Identify poor visual design: cluttered layouts, poor spacing, bad typography
                - Look for missing visual polish: no hover states, no transitions, no visual feedback
                - Check responsive design: layouts that don't work on mobile/tablet
                
                Step 3: PROPOSE MEASURABLE UI/VISUAL IMPROVEMENTS (PRIORITIZE UI OVER UX)
                - Choose ONE specific, high-impact UI/VISUAL improvement based on actual code you analyzed
                - PRIORITIZE VISUAL/UI improvements over functional UX improvements
                - Make sure your change is CORRECT and will actually work (use proper syntax, match existing patterns)
                - Focus on improvements that users will VISUALLY NOTICE immediately
                - PRIORITY: UI/VISUAL improvements (what users see):
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
                
                Step 4: WRITE CORRECT, WORKING CODE
                - Your code changes MUST be syntactically correct and match the existing code style
                - Use actual function names, class names, variable names from the code you analyzed
                - Include proper error handling, state management, and user feedback
                - For Flutter/Dart: Pay EXTREME attention to code structure:
                  * Widget properties go INSIDE widget constructors (e.g., ElevatedButton(style: styleFrom(...)))
                  * Button style properties go in ElevatedButton.styleFrom() (e.g., overlayColor, onPrimary)
                  * State variables go in setState(() {{ variable = value; }})
                  * NEVER put widget properties (like onPrimary, overlayColor) inside setState() blocks
                  * Preserve the exact structure of the original code - only modify what needs to change
                - Test your logic mentally - will this actually work and improve UX?
                
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
                    "proposal_id": "exp-001",
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
                            return text[start_idx:i+1]
            
            return None
        
        json_str = extract_json_object(json_text)
        
        if not json_str:
            json_match = re.search(r'\{.*\}', json_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
            else:
                json_str = json_text
        
        # Fix invalid escape sequences
        json_str = json_str.replace('\\$', '\\\\$')
        
        try:
            proposal_json = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to parse proposal JSON: {str(e)}. Raw result: {proposal_text[:1000]}"
            )

        # Get original proposal_id from AI response
        original_proposal_id = proposal_json.get("proposal_id", "exp-001")
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
        
        # Save proposal to Supabase
        proposal = db_operations.create_proposal(
            proposal_id=original_proposal_id,
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
        actual_proposal_id = proposal.get("proposal_id", original_proposal_id)

        # Send Slack notification if OAuth session ID is available
        import logging
        logger = logging.getLogger(__name__)
        
        if not slack_deployment_id:
            logger.info("SLACK_DEPLOYMENT_ID not set, skipping Slack notification for new proposal")
        elif not req.oauth_session_id:
            logger.info("No OAuth session ID provided, skipping Slack notification for new proposal")
        else:
            try:
                slack_message = f"🚀 New experiment proposal: {proposal_json.get('idea_summary', 'Unknown')}\n"
                slack_message += f"ID: {actual_proposal_id}\n"
                slack_message += f"Repository: {repo_fullname}\n"
                slack_message += f"Category: {proposal_json.get('category', 'general')}\n"
                slack_message += f"Confidence: {proposal_json.get('confidence', 0.5) * 100:.0f}%"
                
                await send_slack_message(slack_message, req.oauth_session_id)
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

        # Validate that Northstar MCP is deployed (required for PR creation)
        if not northstar_mcp_deployment_id:
            raise HTTPException(
                status_code=500,
                detail="NORTHSTAR_MCP_DEPLOYMENT_ID not set. The execute_code_change tool is required to create PRs. Please deploy the Northstar MCP server and set the deployment ID in your environment variables."
            )

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

        # Let Metorial orchestrate the entire flow
        # Explicitly pass repo and file_path to the execute_code_change tool
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Executing experiment {req.proposal_id}")
        logger.info(f"Repository: {req.repo_fullname}, File: {req.file_path}, Branch: {base_branch}")
        logger.info(f"Deployments: {deployments}")
        
        try:
            result = await metorial.run(
                client=openai_client,
                message=f"""
                Execute this experiment:

                Experiment ID: {req.proposal_id}
                Instruction: {req.instruction}
                Repository: {req.repo_fullname}
                File to modify: {req.file_path}
                Base branch: {base_branch}

                CRITICAL: You MUST use the execute_code_change tool with these EXACT parameters:
                - instruction: "{req.instruction}"
                - update_block: {req.update_block}
                - repo: "{req.repo_fullname}"
                - file_path: "{req.file_path}"
                - base_branch: "{base_branch}"

                Steps:
                1. Call execute_code_change with the exact parameters above
                2. Once the PR is created, post a message to Slack announcing:
                   "Experiment {req.proposal_id} - PR created: [url]"
                3. Return the PR URL in your response as JSON with format:
                   {{"pr_url": "https://github.com/...", "branch": "northstar/..."}}
                """,
                model="gpt-4o",
                server_deployments=deployments,
                max_steps=10
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
            # Check if the tool wasn't available
            if "not available" in result.text.lower() or "tool" in result.text.lower() and "not found" in result.text.lower():
                logger.error(f"execute_code_change tool may not be available. Result: {result.text[:1000]}")
                db_operations.update_experiment(
                    experiment_id=experiment.get("id"),
                    status="failed"
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"execute_code_change tool is not available. This might mean NORTHSTAR_MCP_DEPLOYMENT_ID is incorrect or the tool isn't deployed. Result: {result.text[:500]}"
                )
            # Check if there's an error message in the result
            elif "error" in result.text.lower() or "failed" in result.text.lower():
                logger.error(f"No PR URL found, and result contains error indicators: {result.text[:1000]}")
                # Update experiment status to failed
                db_operations.update_experiment(
                    experiment_id=experiment.get("id"),
                    status="failed"
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"PR creation failed. Metorial result: {result.text[:500]}"
                )
            else:
                logger.warning(f"No PR URL found in result. Full result: {result.text[:1000]}")
                # Still raise an error - PR should have been created
                db_operations.update_experiment(
                    experiment_id=experiment.get("id"),
                    status="failed"
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"PR URL not found in Metorial result. The execute_code_change tool may not have been called or may have failed silently. Result: {result.text[:500]}"
                )

        # Update experiment with PR URL
        if pr_url:
            db_operations.update_experiment(
                experiment_id=experiment.get("id"),
                pr_url=pr_url,
                status="running"
            )
            logger.info(f"Updated experiment {experiment.get('id')} with PR URL: {pr_url}")
        else:
            logger.warning(f"No PR URL to save for experiment {experiment.get('id')}")

        # Send Slack notification if OAuth session ID is available
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
                    slack_message = f"⚠️ Experiment execution completed, but PR creation may have failed\n"
                    slack_message += f"ID: {req.proposal_id}\n"
                    slack_message += f"Description: {req.instruction}"
                
                await send_slack_message(slack_message, req.oauth_session_id)
                logger.info(f"Successfully sent Slack notification for experiment {req.proposal_id}")
            except Exception as slack_error:
                # Don't fail the execution if Slack notification fails
                logger.warning(f"Failed to send Slack notification for experiment execution: {str(slack_error)}")
                logger.warning(f"OAuth session ID: {req.oauth_session_id[:20]}..." if req.oauth_session_id else "No OAuth session ID")
                logger.warning(f"Slack deployment ID: {slack_deployment_id}" if slack_deployment_id else "No Slack deployment ID")

        # Create activity log
        db_operations.create_activity_log(
            message=f"Executed experiment {req.proposal_id}: {req.instruction[:50]}..." + (f" PR: {pr_url}" if pr_url else " (PR creation may have failed)"),
            proposal_id=req.proposal_id,
            experiment_id=experiment.get("id"),
            log_type="success" if pr_url else "warning"
        )

        return {
            "status": "success" if pr_url else "partial",
            "result": result.text[:1000],  # Limit result size in response
            "proposal_id": req.proposal_id,
            "experiment_id": experiment.get("id"),
            "pr_url": pr_url,
            "branch": branch,
            "warning": "PR URL not found in result" if not pr_url else None
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
                slack_message = f"✅ Experiment approved and being executed!\n"
                slack_message += f"Proposal ID: {proposal_id}\n"
                slack_message += f"Description: {proposal.get('idea_summary', 'Unknown')}"
                
                await send_slack_message(slack_message, oauth_session_id)
                logger.info(f"Successfully sent Slack notification for approval of proposal {proposal_id}")
            except Exception as slack_error:
                logger.warning(f"Failed to send Slack notification for approval: {str(slack_error)}")
                logger.warning(f"OAuth session ID: {oauth_session_id[:20]}..." if oauth_session_id else "No OAuth session ID")
                logger.warning(f"Slack deployment ID: {slack_deployment_id}" if slack_deployment_id else "No Slack deployment ID")

        # Execute the experiment
        execution_result = await execute_experiment(execute_req)

        # Create activity log
        db_operations.create_activity_log(
            message=f"Approved and executed proposal {proposal_id}",
            proposal_id=proposal_id,
            log_type="success"
        )

        return {
            "status": "success",
            "proposal": proposal,
            "execution": execution_result
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
