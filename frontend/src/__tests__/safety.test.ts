import { getExecutiveRiskTier, getRiskTierLabel, getRiskTierExplanation } from "@/lib/risk-labels";
import { getExecutiveRuleName, getRuleDescription } from "@/lib/rule-labels";
import { getCatalogEntry } from "@/lib/recommendation-catalog";
import { buildRecommendationNarrative } from "@/lib/recommendation-narrative";
import { getSchemaInfo, getFreshnessLevel, getPolicyRoleLabel } from "@/lib/governance-labels";
import { formatNumber, formatPercent, formatDecimal } from "@/lib/format";
import {
  getExecutiveEcosystemSegment,
  getExecutiveDriver,
  getFullActionText,
} from "@/lib/label-resolver";

describe("Safety — NaN Protection", () => {
  it("formatPercent handles NaN gracefully", () => {
    expect(formatPercent(NaN, "en")).toBe("NaN%");
  });

  it("formatNumber handles NaN gracefully", () => {
    const result = formatNumber(NaN, "en");
    expect(result).not.toBe("—");
    expect(typeof result).toBe("string");
  });

  it("formatDecimal handles NaN gracefully", () => {
    const result = formatDecimal(NaN, "en");
    expect(typeof result).toBe("string");
  });
});

describe("Safety — Unknown Risk Tiers", () => {
  it("getExecutiveRiskTier handles empty string", () => {
    expect(getExecutiveRiskTier("")).toBe("—");
  });

  it("getRiskTierLabel handles completely unknown value", () => {
    const result = getRiskTierLabel("nonexistent_tier_value");
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
  });

  it("getRiskTierExplanation handles missing tier", () => {
    expect(getRiskTierExplanation("")).toBe("");
  });
});

describe("Safety — Unknown Rule IDs", () => {
  it("getExecutiveRuleName handles unknown rule gracefully", () => {
    const name = getExecutiveRuleName("R99_NONEXISTENT");
    expect(name).toBe("Retention Play");
  });

  it("getExecutiveRuleName handles empty string", () => {
    expect(getExecutiveRuleName("")).toBe("—");
  });

  it("getRuleDescription handles unknown rule", () => {
    expect(getRuleDescription("R99_NONEXISTENT")).toBe("");
  });

  it("getCatalogEntry returns null for unknown rule", () => {
    expect(getCatalogEntry("R99_NONEXISTENT")).toBeNull();
  });

  it("getCatalogEntry handles null", () => {
    expect(getCatalogEntry(null)).toBeNull();
  });

  it("buildRecommendationNarrative handles unknown rule without crashing", () => {
    const n = buildRecommendationNarrative("R99_NONEXISTENT", "some_action");
    expect(n.businessName).toBe("Retention Play");
    expect(n.executiveSummary).toBeTruthy();
    expect(n.suggestedChannels).toEqual([]);
    expect(n.playbookOffers).toEqual([]);
  });
});

describe("Safety — Partial Payloads", () => {
  it("getSchemaInfo handles partial artifact ID", () => {
    const info = getSchemaInfo("unknown-artifact-id");
    expect(info.technicalId).toBe("unknown-artifact-id");
    expect(info.friendlyName).toBeTruthy();
  });

  it("getFreshnessLevel handles invalid timestamps safely", () => {
    const result = getFreshnessLevel("not-a-valid-timestamp");
    expect(result.level).toBe("stale");
    expect(result.label).toBe("Unknown");
    expect(result.hours).toBe(Infinity);
  });

  it("getFreshnessLevel handles edge case empty string", () => {
    const result = getFreshnessLevel("");
    expect(result.level).toBe("stale");
  });
});

describe("Safety — Missing Governance Fields", () => {
  it("getPolicyRoleLabel handles undefined", () => {
    expect(getPolicyRoleLabel(undefined)).toBe("—");
  });

  it("getPolicyRoleLabel handles empty string", () => {
    expect(getPolicyRoleLabel("")).toBe("—");
  });
});

describe("Safety — Empty/Null Values in Label Resolvers", () => {
  it("getExecutiveEcosystemSegment handles empty string", () => {
    const result = getExecutiveEcosystemSegment("");
    expect(result).toBe("—");
  });

  it("getExecutiveDriver handles empty string", () => {
    const result = getExecutiveDriver("");
    expect(result).toBe("—");
  });

  it("getFullActionText handles empty string", () => {
    const result = getFullActionText("");
    expect(result).toBe("—");
  });
});

describe("Safety — Ecosystem segment key compatibility", () => {
  it("handles fully_adopted legacy alias via mapping", () => {
    const result = getExecutiveEcosystemSegment("fully_adopted");
    expect(result).toBe("Fully Embedded");
  });
});
