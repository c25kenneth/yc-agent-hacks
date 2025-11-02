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
          "Generate an experiment proposal to improve product metrics",
        inputSchema: {},
      },
      async () => {
        return await proposeExperiment();
      }
    );

    // Register execute_code_change tool
    server.registerTool(
      "execute_code_change",
      {
        title: "Execute Code Change",
        description:
          "Execute a code change using Morph Fast Apply and create a GitHub PR",
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

async function proposeExperiment() {
  /**
   * Generate a hardcoded experiment proposal.
   *
   * Returns:
   *   Experiment proposal as JSON
   */
  // Hardcoded proposals for MVP demo
  const proposals = [
    {
      proposal_id: "exp-001",
      idea_summary: "Simplify checkout form by reducing fields from 8 to 4",
      rationale:
        "Competitor analysis shows that simpler checkout flows improve conversion. Removing optional fields reduces friction.",
      expected_impact: {
        metric: "checkout_conversion",
        delta_pct: 0.048,
      },
      technical_plan: [
        {
          file: "checkout.html",
          action: "Remove optional address fields and combine name fields",
        },
      ],
      category: "checkout_optimization",
      confidence: 0.75,
    },
    {
      proposal_id: "exp-002",
      idea_summary: "Add trust badges below payment button",
      rationale:
        "Security concerns are a top barrier to conversion. Trust badges from SSL provider can increase confidence.",
      expected_impact: {
        metric: "checkout_conversion",
        delta_pct: 0.032,
      },
      technical_plan: [
        {
          file: "checkout.html",
          action: "Add SSL badge and money-back guarantee icon below CTA",
        },
      ],
      category: "trust_building",
      confidence: 0.68,
    },
    {
      proposal_id: "exp-003",
      idea_summary: "Optimize button color for higher visibility",
      rationale:
        "Current button (#3b82f6) has low contrast ratio. Increasing to high-contrast green can improve click rate.",
      expected_impact: {
        metric: "cta_click_rate",
        delta_pct: 0.056,
      },
      technical_plan: [
        {
          file: "styles.css",
          action:
            "Change primary button color from blue to high-contrast green (#10b981)",
        },
      ],
      category: "ui_optimization",
      confidence: 0.62,
    },
  ];

  // Return first proposal for demo
  const proposal = proposals[0];

  return {
    content: [
      {
        type: "text",
        text: JSON.stringify(proposal, null, 2),
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
