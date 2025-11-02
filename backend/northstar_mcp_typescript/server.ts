/** Northstar MCP Server - Custom tools for AI-powered experimentation. */

import { z, metorial } from "@metorial/mcp-server-sdk";

import { mergeCode, MorphAPIError } from "./morph_client.ts";
import {
  cloneRepo,
  ensureBranch,
  createCommitAndPush,
  cleanupRepo,
} from "./git_ops.ts";
import { openPR } from "./github_ops.ts";
import { slugify, unifiedDiff, formatPRBody } from "./utils.ts";

interface Config {
  // Environment variables are accessed via Deno.env.get()
  // token: string;
}

metorial.createServer<Config>(
  {
    name: "northstar-mcp",
    version: "0.1.0",
  },
  async (server, args) => {
    // Register propose_experiment tool
    server.registerTool(
      "propose_experiment",
      {
        title: "Propose Experiment",
        description:
          "Generate an experiment proposal with UI/visual code changes to improve product metrics. FOCUS ON UI ADJUSTMENTS: styling, layout, colors, spacing, typography, visual hierarchy, button styling, form styling, responsive design, hover states, transitions, and visual polish. Requires codebase context to analyze and propose specific UI improvements with code changes.",
        inputSchema: {
          codebase_context: z.string().optional().describe(
            "Repository codebase context or code snippets to analyze. This should include actual UI/styling code from the repository (CSS, Tailwind classes, inline styles, component styling, HTML structure, React/Flutter UI components) so the tool can propose specific UI/visual improvements with code changes."
          ),
          repo_fullname: z.string().optional().describe(
            "Repository name in format 'owner/repo' (optional, for reference)"
          ),
        },
      },
      async ({ codebase_context, repo_fullname }) => {
        return await proposeExperiment(codebase_context, repo_fullname);
      }
    );

    // Register execute_code_change tool
    server.registerTool(
      "execute_code_change",
      {
        title: "Execute Code Change",
        description:
          "Execute a code change using Morph Fast Apply and create a GitHub PR. This tool has full access to Git, GitHub API, and Morph API. It can clone repositories, modify files, create branches, push changes, and create pull requests. Use this tool to execute code changes - it has all required access to external systems.",
        inputSchema: {
          instruction: z.string().describe(
            "Natural language description of the code change"
          ),
          update_block: z.string().describe(
            "Fast Apply format code snippet with '// ... existing code ...' markers"
          ),
          repo: z.string().optional().describe(
            "Repository name in format 'owner/repo' (optional, uses env default)"
          ),
          file_path: z.string().optional().describe(
            "Path to file to modify (optional, uses env default)"
          ),
          base_branch: z.string().optional().default("main").describe(
            "Base branch to merge into (default: main)"
          ),
        },
      },
      async ({ instruction, update_block, repo, file_path, base_branch }) => {
        return await executeCodeChange(
          instruction,
          update_block,
          repo,
          file_path,
          base_branch || "main"
        );
      }
    );
  }
);

async function proposeExperiment(
  codebaseContext?: string,
  repoFullname?: string
) {
  /**
   * Generate an experiment proposal with actual code changes.
   *
   * Args:
   *   codebaseContext: Repository codebase context or code snippets to analyze
   *   repoFullname: Repository name for reference
   *
   * Returns:
   *   Experiment proposal as JSON with update_block containing actual code changes
   */
  
  // If no codebase context provided, return error message
  if (!codebaseContext || codebaseContext.trim().length === 0) {
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            error: "codebase_context_required",
            message: "This tool requires codebase context to analyze and propose specific code improvements. Please provide actual code from the repository (not just repository metadata or file listings). The codebase_context should include source code files (JavaScript, TypeScript, Python, Dart, HTML, CSS, etc.) so I can analyze the actual code and propose specific improvements with code changes.",
            hint: "Include actual source code files in the codebase_context parameter. You can fetch repository files using GitHub APIs or other code fetching tools before calling this tool.",
          }, null, 2),
        },
      ],
    };
  }

  // Echo the codebase context back with instructions
  // This makes it clear to Metorial that the code is already provided
  const fullContext = codebaseContext.length > 20000 
    ? codebaseContext.substring(0, 20000) + `\n\n... (${codebaseContext.length - 20000} more characters truncated for display)`
    : codebaseContext;
    
  const responseMessage = `CODEBASE CONTEXT FOR ${repoFullname || "the repository"}:

This is the ACTUAL repository code that was fetched and provided to you. You MUST analyze this code to generate a proposal. The code is already provided below - you don't need to fetch anything.

=== REPOSITORY CODE (ANALYZE THIS) ===

${fullContext}

=== YOUR TASK ===

1. ANALYZE the code above - look for UI/styling code (CSS, Tailwind classes, inline styles, component styling)
2. IDENTIFY UI/visual problems (styling issues, layout problems, visual design flaws)
3. GENERATE proposal JSON with ACTUAL code changes

CRITICAL: FOCUS ON UI/VISUAL ADJUSTMENTS ONLY (styling, layout, colors, typography, hover states, visual polish)
IGNORE: Functional logic, backend code, configuration files

Return ONLY this JSON (no explanations, no markdown, no text before/after):
{"proposal_id":"exp-unique","idea_summary":"Specific UI improvement based on code analysis","rationale":"Detailed explanation of UI problem found","expected_impact":{"metric":"click_rate","delta_pct":0.05},"technical_plan":[{"file":"path/to/style/file.ext","action":"Styling change description"}],"update_block":"ACTUAL CODE with +/- markers showing styling changes","category":"ui_optimization","confidence":0.8}

The update_block MUST contain actual code with +/- markers, not instructions.`;

  return {
    content: [
      {
        type: "text",
        text: responseMessage,
      },
    ],
  };
}

async function executeCodeChange(
  instruction: string,
  updateBlock: string,
  repo?: string,
  filePath?: string,
  baseBranch: string = "main"
) {
  /**
   * Execute a code change using Morph Fast Apply and create a GitHub PR.
   *
   * Args:
   *   instruction: Natural language description of the change
   *   updateBlock: Fast Apply format code snippet
   *   repo: Repository name (owner/repo) - uses TARGET_REPO env if not provided
   *   filePath: Path to file to modify - uses TARGET_FILE env if not provided
   *   baseBranch: Base branch to merge into (default: main)
   *
   * Returns:
   *   PR URL and execution details
   */
  // Use env vars as defaults
  const targetRepo = repo || Deno.env.get("TARGET_REPO");
  const targetFile = filePath || Deno.env.get("TARGET_FILE");

  if (!targetRepo) {
    return {
      content: [
        {
          type: "text",
          text: "Error: TARGET_REPO not set in environment and not provided as argument",
        },
      ],
    };
  }

  if (!targetFile) {
    return {
      content: [
        {
          type: "text",
          text: "Error: TARGET_FILE not set in environment and not provided as argument",
        },
      ],
    };
  }

  let repoPath: string | null = null;
  try {
    // Clone repository
    repoPath = await cloneRepo(targetRepo);

    // Read current file
    const fileFullPath = `${repoPath}/${targetFile}`;
    try {
      await Deno.stat(fileFullPath);
    } catch {
      return {
        content: [
          {
            type: "text",
            text: `Error: File ${targetFile} not found in repository`,
          },
        ],
      };
    }

    const currentContent = await Deno.readTextFile(fileFullPath);

    // Call Morph API to merge code
    let mergedContent: string;
    try {
      mergedContent = await mergeCode(
        instruction,
        currentContent,
        updateBlock
      );
    } catch (e) {
      if (e instanceof MorphAPIError) {
        return {
          content: [
            {
              type: "text",
              text: `Morph API Error: ${e.message}`,
            },
          ],
        };
      }
      throw e;
    }

    // Generate diff
    const diff = unifiedDiff(currentContent, mergedContent, targetFile);

    if (!diff) {
      return {
        content: [
          {
            type: "text",
            text: "No changes detected - merged code is identical to original",
          },
        ],
      };
    }

    // Write merged content
    await Deno.writeTextFile(fileFullPath, mergedContent);

    // Git operations
    const branchSlug = slugify(instruction);
    const branchName = `northstar/${branchSlug}`;
    const finalBranch = await ensureBranch(repoPath, baseBranch, branchName);

    const commitMessage = `Northstar: ${instruction}`;
    await createCommitAndPush(repoPath, finalBranch, commitMessage);

    // Create PR
    const prTitle = `Northstar Experiment: ${instruction}`;
    const prBody = formatPRBody(instruction, targetFile, diff);
    const prUrl = await openPR(
      targetRepo,
      finalBranch,
      baseBranch,
      prTitle,
      prBody
    );

    // Success
    const result = {
      status: "success",
      pr_url: prUrl,
      branch: finalBranch,
      files_modified: [targetFile],
      diff_summary: `${diff.split("\n").length} lines changed`,
    };

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(result, null, 2),
        },
      ],
    };
  } catch (e) {
    return {
      content: [
        {
          type: "text",
          text: `Error executing code change: ${e instanceof Error ? e.message : String(e)}`,
        },
      ],
    };
  } finally {
    // Cleanup
    if (repoPath) {
      await cleanupRepo(repoPath);
    }
  }
}
