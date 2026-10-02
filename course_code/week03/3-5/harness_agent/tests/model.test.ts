import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("Gateway model alias", () => {
  it("preserves the course alias when no override is configured", async () => {
    vi.stubEnv("GATEWAY_MODEL", undefined);
    const { gatewayModel } = await import("../src/model.js");
    expect(gatewayModel.id).toBe("agent-default");
  });

  it("registers the configured gateway alias with the provider", async () => {
    vi.stubEnv("GATEWAY_MODEL", "smart");
    const { gatewayModel, models } = await import("../src/model.js");
    expect(gatewayModel.id).toBe("smart");
    expect(models.getModel(gatewayModel.provider, "smart")).toEqual(gatewayModel);
  });

  it("falls back for an empty alias", async () => {
    vi.stubEnv("GATEWAY_MODEL", "  ");
    const { gatewayModel } = await import("../src/model.js");
    expect(gatewayModel.id).toBe("agent-default");
  });
});
