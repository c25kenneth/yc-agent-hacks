/** GitHub operations for creating pull requests. */

/**
 * Create a pull request on GitHub, or return existing PR URL if one exists.
 *
 * @param repoFullname Repository in format 'owner/repo'
 * @param headBranch Source branch (the new changes)
 * @param baseBranch Target branch (usually 'main')
 * @param title PR title
 * @param body PR description
 * @returns URL of the created or existing pull request
 * @throws Error if PR creation fails
 */
export async function openPR(
  repoFullname: string,
  headBranch: string,
  baseBranch: string,
  title: string,
  body: string
): Promise<string> {
  const githubToken = Deno.env.get("GITHUB_TOKEN");

  if (!githubToken) {
    throw new Error(
      "GITHUB_TOKEN not found in environment.\n" +
        "Hint: Set it in your .env file or environment variables."
    );
  }

  try {
    const [owner, repo] = repoFullname.split("/");
    if (!owner || !repo) {
      throw new Error(
        `Invalid repository format: ${repoFullname}. Expected 'owner/repo'`
      );
    }

    // Check if PR already exists for this branch
    const existingPRsUrl = `https://api.github.com/repos/${repoFullname}/pulls?state=open&head=${owner}:${headBranch}`;
    const existingPRsResponse = await fetch(existingPRsUrl, {
      headers: {
        Authorization: `token ${githubToken}`,
        Accept: "application/vnd.github.v3+json",
      },
    });

    if (existingPRsResponse.ok) {
      const existingPRs = await existingPRsResponse.json();
      if (Array.isArray(existingPRs) && existingPRs.length > 0) {
        return existingPRs[0].html_url;
      }
    }

    // Create new PR
    const createPRUrl = `https://api.github.com/repos/${repoFullname}/pulls`;
    const createPRResponse = await fetch(createPRUrl, {
      method: "POST",
      headers: {
        Authorization: `token ${githubToken}`,
        Accept: "application/vnd.github.v3+json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        title,
        body,
        base: baseBranch,
        head: headBranch,
      }),
    });

    if (!createPRResponse.ok) {
      const errorData = await createPRResponse.json().catch(() => ({}));
      const status = createPRResponse.status;
      let errorMsg = `GitHub API error: ${errorData.message || createPRResponse.statusText}`;

      if (status === 401) {
        errorMsg += "\nHint: Your GITHUB_TOKEN may be invalid or expired.";
      } else if (status === 404) {
        errorMsg +=
          `\nHint: Repository '${repoFullname}' not found or you don't have access.`;
      } else if (status === 422) {
        errorMsg +=
          "\nHint: Check that base and head branches are different and exist.";
      }

      throw new Error(errorMsg);
    }

    const prData = await createPRResponse.json();
    return prData.html_url;
  } catch (e) {
    if (e instanceof Error) {
      throw e;
    }
    throw new Error(`Failed to create pull request: ${String(e)}`);
  }
}

