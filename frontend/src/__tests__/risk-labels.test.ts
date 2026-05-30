import {
  getExecutiveRiskTier,
  getRiskTierLabel,
  getRiskTierExplanation,
  RISK_TIER_MAP,
  RISK_TIER_VALUES,
  RISK_TIER_BUSINESS_LABELS,
} from "@/lib/risk-labels";

describe("Risk Labels", () => {
  describe("getExecutiveRiskTier", () => {
    it("maps Very High to Critical", () => {
      expect(getExecutiveRiskTier("Very High")).toBe("Critical");
    });
    it("maps High to At Risk", () => {
      expect(getExecutiveRiskTier("High")).toBe("At Risk");
    });
    it("maps Medium to Watchlist", () => {
      expect(getExecutiveRiskTier("Medium")).toBe("Watchlist");
    });
    it("maps Low to Stable", () => {
      expect(getExecutiveRiskTier("Low")).toBe("Stable");
    });
    it("returns em dash for null", () => {
      expect(getExecutiveRiskTier(null)).toBe("—");
    });
    it("returns em dash for undefined", () => {
      expect(getExecutiveRiskTier(undefined as unknown as null)).toBe("—");
    });
    it("passes through unknown tiers", () => {
      expect(getExecutiveRiskTier("Unknown")).toBe("Unknown");
    });
    it("returns original value for unmapped tier", () => {
      expect(getExecutiveRiskTier("CustomTier")).toBe("CustomTier");
    });
  });

  describe("getRiskTierLabel", () => {
    it("maps snake_case critical to Critical", () => {
      expect(getRiskTierLabel("critical")).toBe("Critical");
    });
    it("maps snake_case very_high to Critical", () => {
      expect(getRiskTierLabel("very_high")).toBe("Critical");
    });
    it("maps snake_case high to At Risk", () => {
      expect(getRiskTierLabel("high")).toBe("At Risk");
    });
    it("maps snake_case medium to Watchlist", () => {
      expect(getRiskTierLabel("medium")).toBe("Watchlist");
    });
    it("maps snake_case low to Stable", () => {
      expect(getRiskTierLabel("low")).toBe("Stable");
    });
    it("humanizes unknown snake_case values", () => {
      expect(getRiskTierLabel("some_custom_tier")).toBe("Some Custom Tier");
    });
  });

  describe("getRiskTierExplanation", () => {
    it("returns explanation for critical", () => {
      const exp = getRiskTierExplanation("critical");
      expect(exp).toContain("Immediate");
      expect(exp).toContain("retention");
    });
    it("returns explanation for very_high", () => {
      const exp = getRiskTierExplanation("very_high");
      expect(exp).toContain("Immediate");
    });
    it("returns explanation for high", () => {
      const exp = getRiskTierExplanation("high");
      expect(exp).toContain("proactive");
    });
    it("returns empty string for unknown", () => {
      expect(getRiskTierExplanation("unknown")).toBe("");
    });
  });

  describe("RISK_TIER_MAP completeness", () => {
    it("maps all four canonical tiers", () => {
      expect(Object.keys(RISK_TIER_MAP)).toEqual(["Very High", "High", "Medium", "Low"]);
    });
    it("maps to Critical, At Risk, Watchlist, Stable", () => {
      expect(Object.values(RISK_TIER_MAP)).toEqual([
        RISK_TIER_VALUES.CRITICAL,
        RISK_TIER_VALUES.AT_RISK,
        RISK_TIER_VALUES.WATCHLIST,
        RISK_TIER_VALUES.STABLE,
      ]);
    });
  });

  describe("RISK_TIER_BUSINESS_LABELS", () => {
    it("maps critical and very_high to Critical", () => {
      expect(RISK_TIER_BUSINESS_LABELS.critical).toBe("Critical");
      expect(RISK_TIER_BUSINESS_LABELS.very_high).toBe("Critical");
    });
    it("covers all expected keys", () => {
      const keys = ["critical", "very_high", "high", "medium", "low"];
      keys.forEach((k) => {
        expect(RISK_TIER_BUSINESS_LABELS[k]).toBeDefined();
      });
    });
  });
});
