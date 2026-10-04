import type { StreamFn } from "@earendil-works/pi-agent-core";
// 官方直连接入层：注册模型、读取鉴权；工具执行与完成判断由 Agent Runtime 负责。
import {
  createModels, createProvider, envApiKeyAuth, type Model,
} from "@earendil-works/pi-ai";
import { openAICompletionsApi } from "@earendil-works/pi-ai/api/openai-completions.lazy";

export function resolveDeepSeekBaseUrl(env: NodeJS.ProcessEnv = process.env): string {
  const configured = env.DEEPSEEK_BASE_URL?.trim() || "https://api.deepseek.com/v1";
  let url: URL;
  try {
    url = new URL(configured);
  } catch {
    throw new Error("DEEPSEEK_BASE_URL 不是有效的官方 URL");
  }
  // 这里约定官网直连。错误地址在启动时失败，避免把官方密钥发给其他主机。
  if (url.origin !== "https://api.deepseek.com" || url.username || url.password
    || url.search || url.hash || !["", "/", "/v1", "/v1/"].includes(url.pathname)) {
    throw new Error("DEEPSEEK_BASE_URL 必须是 https://api.deepseek.com 或其 /v1 路径");
  }
  return "https://api.deepseek.com/v1";
}

export const deepseekModel: Model<"openai-completions"> = {
  id: process.env.DEEPSEEK_MODEL?.trim() || "deepseek-flash",
  name: "DeepSeek Flash",
  provider: "deepseek",
  api: "openai-completions",
  baseUrl: resolveDeepSeekBaseUrl(),
  // reasoning 声明供应商能力。pi 在未指定 reasoningEffort 时显式发送 thinking: disabled。
  // 若设为 false，适配器会省略该字段，反而触发供应商默认的思考模式。
  reasoning: true,
  compat: {
    thinkingFormat: "deepseek",
    requiresReasoningContentOnAssistantMessages: true,
    maxTokensField: "max_tokens",
  },
  input: ["text"],
  // 类型要求的占位值，未接入计费统计；0 不代表调用免费。
  cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
  // 课程的上下文/输出预算，不代表供应商最大能力。
  contextWindow: 128_000,
  maxTokens: 4096,
};

const provider = createProvider({
  id: "deepseek",
  name: "DeepSeek Official",
  baseUrl: deepseekModel.baseUrl,
  auth: { apiKey: envApiKeyAuth("DeepSeek API key", ["DEEPSEEK_API_KEY"]) },
  models: [deepseekModel],
  api: openAICompletionsApi(),
});

export const models = createModels();
models.setProvider(provider);

export const streamDeepSeek: StreamFn = models.streamSimple.bind(models);
