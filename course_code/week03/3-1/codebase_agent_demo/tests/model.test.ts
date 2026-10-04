import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

beforeEach(() => {
  vi.resetModules();
  for (const name of ["DEEPSEEK_MODEL", "DEEPSEEK_BASE_URL", "DEEPSEEK_API_KEY"]) {
    vi.stubEnv(name, undefined);
  }
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("DeepSeek official connection", () => {
  it("defaults to the requested model at the official endpoint", async () => {
    const { deepseekModel } = await import("../src/model.js");
    expect(deepseekModel).toMatchObject({
      id: "deepseek-flash", provider: "deepseek",
      baseUrl: "https://api.deepseek.com/v1", reasoning: true,
      compat: { thinkingFormat: "deepseek", maxTokensField: "max_tokens" },
    });
  });

  it("registers a trimmed model override", async () => {
    vi.stubEnv("DEEPSEEK_MODEL", " deepseek-flash ");
    const { deepseekModel, models } = await import("../src/model.js");
    expect(deepseekModel.id).toBe("deepseek-flash");
    expect(models.getModel("deepseek", "deepseek-flash")).toEqual(deepseekModel);
  });

  it("uses the default for a blank model", async () => {
    vi.stubEnv("DEEPSEEK_MODEL", "  ");
    const { deepseekModel } = await import("../src/model.js");
    expect(deepseekModel.id).toBe("deepseek-flash");
  });

  it("normalizes the official root URL", async () => {
    vi.stubEnv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/");
    const { deepseekModel } = await import("../src/model.js");
    expect(deepseekModel.baseUrl).toBe("https://api.deepseek.com/v1");
  });

  it.each([
    "http://api.deepseek.com/v1", "https://other.example/v1",
    "https://api.deepseek.com/anthropic", "https://user@api.deepseek.com/v1",
    "https://api.deepseek.com/v1?key=example", "not-a-url",
  ])("rejects an endpoint outside the official Chat API: %s", async (url) => {
    vi.stubEnv("DEEPSEEK_BASE_URL", url);
    await expect(import("../src/model.js")).rejects.toThrow("DEEPSEEK_BASE_URL");
  });

  it("resolves only DEEPSEEK_API_KEY for provider authentication", async () => {
    vi.stubEnv("DEEPSEEK_API_KEY", "test-deepseek-key");
    vi.stubEnv("GATEWAY_API_KEY", "different-key");
    const { deepseekModel, models } = await import("../src/model.js");
    const auth = await models.getAuth(deepseekModel);
    expect(auth?.auth.apiKey).toBe("test-deepseek-key");
  });

  it("sends an explicit non-thinking request and consumes the SSE result", async () => {
    vi.stubEnv("DEEPSEEK_API_KEY", "test-deepseek-key");
    const { deepseekModel, models } = await import("../src/model.js");
    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      const request = new Request(input, init);
      expect(request.url).toBe("https://api.deepseek.com/v1/chat/completions");
      expect(request.headers.get("authorization")).toBe("Bearer test-deepseek-key");
      const body = await request.json();
      expect(body).toMatchObject({
        model: "deepseek-flash", stream: true, max_tokens: 32,
        thinking: { type: "disabled" },
      });
      expect(body).not.toHaveProperty("max_completion_tokens");
      const chunk = {
        id: "test", object: "chat.completion.chunk", created: 0,
        model: "deepseek-flash",
        choices: [{ index: 0, delta: { role: "assistant", content: "连接成功" }, finish_reason: "stop" }],
      };
      return new Response(`data: ${JSON.stringify(chunk)}\n\ndata: [DONE]\n\n`, {
        headers: { "content-type": "text/event-stream" },
      });
    });
    const result = await models.streamSimple(deepseekModel, {
      messages: [{ role: "user", content: "测试连接", timestamp: 0 }],
    }, { fetch: fetchMock, maxTokens: 32, maxRetries: 0 }).result();
    expect(result.stopReason).toBe("stop");
    expect(result.content).toEqual([{ type: "text", text: "连接成功" }]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
