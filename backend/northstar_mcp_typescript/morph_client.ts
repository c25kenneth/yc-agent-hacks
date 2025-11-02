/** Morph API client for Fast Apply code merging. */

export class MorphAPIError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "MorphAPIError";
  }
}

/**
 * Merge code using Morph's Fast Apply API.
 *
 * @param instruction Natural language description of the changes
 * @param initialCode Current file contents
 * @param updateBlock Fast Apply format update with '// ... existing code ...' markers
 * @returns Merged code as a string
 * @throws MorphAPIError If API call fails or returns invalid response
 */
export async function mergeCode(
  instruction: string,
  initialCode: string,
  updateBlock: string
): Promise<string> {
  const apiKey = Deno.env.get("MORPH_API_KEY");
  const baseUrl = Deno.env.get("MORPH_BASE_URL") || "https://api.morphllm.com/v1";

  if (!apiKey) {
    throw new MorphAPIError(
      "MORPH_API_KEY not found in environment. " +
        "Please set it in your .env file or environment variables."
    );
  }

  // Construct the user message content in Morph Fast Apply format
  const content =
    `<instruction>${instruction}</instruction>\n` +
    `<code>${initialCode}</code>\n` +
    `<update>${updateBlock}</update>`;

  // Prepare API request
  const url = `${baseUrl}/chat/completions`;
  const headers = {
    Authorization: `Bearer ${apiKey}`,
    "Content-Type": "application/json",
  };
  const payload = {
    model: "morph-v3-fast",
    messages: [
      {
        role: "user",
        content: content,
      },
    ],
  };

  let response: Response;
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    response = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new MorphAPIError("Request to Morph API timed out after 30 seconds");
    }
    throw new MorphAPIError(`Morph API request failed: ${String(e)}`);
  }

  if (!response.ok) {
    let errorMsg = `Morph API request failed with status ${response.status}`;
    try {
      const errorDetail = await response.json();
      errorMsg += `\nAPI response: ${JSON.stringify(errorDetail)}`;
    } catch {
      errorMsg += `\nStatus code: ${response.status}`;
    }
    throw new MorphAPIError(errorMsg);
  }

  // Parse response
  try {
    const data = await response.json();
    const mergedCode = data.choices?.[0]?.message?.content;

    if (!mergedCode || !mergedCode.trim()) {
      throw new MorphAPIError(
        "Morph API returned empty content. " + `Full response: ${JSON.stringify(data)}`
      );
    }

    return mergedCode;
  } catch (e) {
    if (e instanceof MorphAPIError) {
      throw e;
    }
    throw new MorphAPIError(
      `Unexpected Morph API response format: ${String(e)}`
    );
  }
}

