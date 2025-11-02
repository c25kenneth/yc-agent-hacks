/** Git operations for cloning, branching, committing, and pushing. */

/**
 * Clone a GitHub repository to a temporary directory.
 *
 * @param repoFullname Repository in format 'owner/repo'
 * @returns Path to the cloned repository
 * @throws Error if clone fails
 */
export async function cloneRepo(repoFullname: string): Promise<string> {
  const tempDir = await Deno.makeTempDir({ prefix: "northstar_" });
  const githubToken = Deno.env.get("GITHUB_TOKEN");
  
  // Build clone URL with token if available (for private repos or authenticated cloning)
  let cloneUrl: string;
  if (githubToken) {
    cloneUrl = `https://${githubToken}@github.com/${repoFullname}.git`;
  } else {
    cloneUrl = `https://github.com/${repoFullname}.git`;
  }

  const cloneCmd = new Deno.Command("git", {
    args: ["clone", cloneUrl, tempDir],
    stdout: "piped",
    stderr: "piped",
  });

  const { code, stderr } = await cloneCmd.output();

  if (code !== 0) {
    const errorText = new TextDecoder().decode(stderr);
    await Deno.remove(tempDir, { recursive: true }).catch(() => {});
    throw new Error(
      `Failed to clone repository '${repoFullname}'.\n` +
        `Error: ${errorText}\n` +
        `Hint: Verify the repository exists and is accessible.`
    );
  }

  // Configure remote URL with token for authenticated pushes
  if (githubToken) {
    const setRemoteCmd = new Deno.Command("git", {
      args: ["remote", "set-url", "origin", `https://${githubToken}@github.com/${repoFullname}.git`],
      cwd: tempDir,
      stdout: "piped",
      stderr: "piped",
    });
    await setRemoteCmd.output();
  }

  return tempDir;
}

/**
 * Create a unique branch name, appending -v2, -v3, etc. if branch exists.
 *
 * @param repoPath Path to the git repository
 * @param baseBranch Base branch to branch from (e.g., 'main')
 * @param newBranch Desired new branch name
 * @returns Final unique branch name that was created
 * @throws Error if checkout or branch creation fails
 */
export async function ensureBranch(
  repoPath: string,
  baseBranch: string,
  newBranch: string
): Promise<string> {
  // Ensure we're on the base branch
  const checkoutBaseCmd = new Deno.Command("git", {
    args: ["checkout", baseBranch],
    cwd: repoPath,
    stdout: "piped",
    stderr: "piped",
  });

  const { code, stderr } = await checkoutBaseCmd.output();

  if (code !== 0) {
    const errorText = new TextDecoder().decode(stderr);
    throw new Error(
      `Failed to checkout base branch '${baseBranch}'.\n` +
        `Error: ${errorText}\n` +
        `Hint: Verify that '${baseBranch}' exists in the repository.`
    );
  }

  // Find unique branch name
  let finalBranch = newBranch;
  let counter = 2;

  while (true) {
    const checkBranchCmd = new Deno.Command("git", {
      args: ["rev-parse", "--verify", finalBranch],
      cwd: repoPath,
      stdout: "piped",
      stderr: "piped",
    });

    const { code } = await checkBranchCmd.output();

    if (code === 0) {
      // Branch exists, try next version
      finalBranch = `${newBranch}-v${counter}`;
      counter++;
    } else {
      // Branch doesn't exist, we can use it
      break;
    }
  }

  // Create and checkout the new branch
  const createBranchCmd = new Deno.Command("git", {
    args: ["checkout", "-b", finalBranch],
    cwd: repoPath,
    stdout: "piped",
    stderr: "piped",
  });

  const { code: createCode, stderr: createStderr } =
    await createBranchCmd.output();

  if (createCode !== 0) {
    const errorText = new TextDecoder().decode(createStderr);
    throw new Error(
      `Failed to create branch '${finalBranch}'.\n` +
        `Error: ${errorText}`
    );
  }

  return finalBranch;
}

/**
 * Stage all changes, create a commit, and push to remote.
 *
 * @param repoPath Path to the git repository
 * @param branch Branch name to push
 * @param message Commit message
 * @throws Error if commit or push fails
 */
export async function createCommitAndPush(
  repoPath: string,
  branch: string,
  message: string
): Promise<void> {
  try {
    // Stage all changes
    const addCmd = new Deno.Command("git", {
      args: ["add", "-A"],
      cwd: repoPath,
      stdout: "piped",
      stderr: "piped",
    });

    await addCmd.output();

    // Check if there are changes to commit
    const statusCmd = new Deno.Command("git", {
      args: ["status", "--porcelain"],
      cwd: repoPath,
      stdout: "piped",
      stderr: "piped",
    });

    const { stdout } = await statusCmd.output();
    const statusText = new TextDecoder().decode(stdout);

    if (!statusText.trim()) {
      // No changes to commit
      return;
    }

    // Create commit
    const commitCmd = new Deno.Command("git", {
      args: ["commit", "-m", message],
      cwd: repoPath,
      stdout: "piped",
      stderr: "piped",
    });

    const { code: commitCode, stderr: commitStderr } = await commitCmd.output();

    if (commitCode !== 0) {
      const errorText = new TextDecoder().decode(commitStderr);
      throw new Error(
        `Failed to create commit.\n` + `Error: ${errorText}`
      );
    }

    // Push to remote
    const pushCmd = new Deno.Command("git", {
      args: ["push", "origin", branch],
      cwd: repoPath,
      stdout: "piped",
      stderr: "piped",
    });

    const { code: pushCode, stderr: pushStderr } = await pushCmd.output();

    if (pushCode !== 0) {
      const errorText = new TextDecoder().decode(pushStderr);
      throw new Error(
        `Failed to commit and push changes.\n` +
          `Error: ${errorText}\n` +
          `Hint: Ensure you have write access to the repository.`
      );
    }
  } catch (e) {
    if (e instanceof Error) {
      throw e;
    }
    throw new Error(`Failed to commit and push changes: ${String(e)}`);
  }
}

/**
 * Clean up cloned repository directory.
 *
 * @param repoPath Path to repository to remove
 */
export async function cleanupRepo(repoPath: string): Promise<void> {
  try {
    await Deno.remove(repoPath, { recursive: true });
  } catch {
    // Best effort cleanup - ignore errors
  }
}

