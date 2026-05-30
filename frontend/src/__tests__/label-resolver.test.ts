import {
  getExecutiveEcosystemSegment,
  getExecutivePriority,
  getExecutiveDriver,
  getFullActionText,
  getCostTierLabel,
  getCrmQueueLabel,
  getInterventionTypeLabel,
  getRetentionStrategyLabel,
  getEngagementLevelLabel,
} from "@/lib/label-resolver";

describe("Label Resolver", () => {
  describe("getExecutiveEcosystemSegment", () => {
    it("maps non_ecosystem correctly", () => {
      expect(getExecutiveEcosystemSegment("non_ecosystem")).toBe("Non-Ecosystem");
    });
    it("maps fully_embedded correctly", () => {
      expect(getExecutiveEcosystemSegment("fully_embedded")).toBe("Fully Embedded");
    });
    it("returns em dash for null", () => {
      expect(getExecutiveEcosystemSegment(null)).toBe("—");
    });
    it("returns em dash for undefined", () => {
      expect(getExecutiveEcosystemSegment(undefined)).toBe("—");
    });
    it("humanizes unknown segment", () => {
      expect(getExecutiveEcosystemSegment("custom_segment")).toBe("Custom Segment");
    });
    it("maps rubika_only correctly", () => {
      expect(getExecutiveEcosystemSegment("rubika_only")).toBe("Rubika Only");
    });
  });

  describe("getExecutivePriority", () => {
    it("maps P1 correctly", () => {
      expect(getExecutivePriority("P1")).toBe("Critical Priority");
    });
    it("maps P2 correctly", () => {
      expect(getExecutivePriority("P2")).toBe("High Priority");
    });
    it("returns em dash for null", () => {
      expect(getExecutivePriority(null)).toBe("—");
    });
    it("passes through unknown priority", () => {
      expect(getExecutivePriority("P5")).toBe("P5");
    });
  });

  describe("getExecutiveDriver", () => {
    it("maps monthly_spend correctly", () => {
      expect(getExecutiveDriver("monthly_spend")).toBe("Monthly Spend");
    });
    it("returns em dash for null", () => {
      expect(getExecutiveDriver(null)).toBe("—");
    });
    it("handles case insensitivity", () => {
      expect(getExecutiveDriver("MONTHLY_SPEND")).toBe("Monthly Spend");
    });
    it("passes through unknown driver", () => {
      expect(getExecutiveDriver("unknown_field")).toBe("unknown_field");
    });
  });

  describe("getFullActionText", () => {
    it("maps incentivize correctly", () => {
      expect(getFullActionText("incentivize")).toContain("incentive");
    });
    it("maps escalate correctly", () => {
      expect(getFullActionText("escalate")).toContain("Escalate");
    });
    it("returns em dash for null", () => {
      expect(getFullActionText(null)).toBe("—");
    });
    it("returns em dash for undefined", () => {
      expect(getFullActionText(undefined)).toBe("—");
    });
    it("returns long text as-is", () => {
      const longText = "a".repeat(100);
      expect(getFullActionText(longText)).toBe(longText);
    });
    it("partial matches embedded action keys", () => {
      const result = getFullActionText("cross_sell_v2");
      expect(result).toContain("Cross-sell");
    });
    it("maps educate correctly", () => {
      expect(getFullActionText("educate")).toContain("educational");
    });
  });

  describe("getCostTierLabel", () => {
    it("maps low correctly", () => {
      expect(getCostTierLabel("low")).toBe("Budget");
    });
    it("maps medium correctly", () => {
      expect(getCostTierLabel("medium")).toBe("Standard");
    });
    it("maps high correctly", () => {
      expect(getCostTierLabel("high")).toBe("Premium");
    });
    it("returns em dash for null", () => {
      expect(getCostTierLabel(null)).toBe("—");
    });
  });

  describe("getCrmQueueLabel", () => {
    it("maps standard correctly", () => {
      expect(getCrmQueueLabel("standard")).toBe("Main Queue");
    });
    it("maps vip correctly", () => {
      expect(getCrmQueueLabel("vip")).toBe("VIP Queue");
    });
    it("returns em dash for null", () => {
      expect(getCrmQueueLabel(null)).toBe("—");
    });
  });

  describe("getInterventionTypeLabel", () => {
    it("maps digital correctly", () => {
      expect(getInterventionTypeLabel("digital")).toBe("Digital Outreach");
    });
    it("maps human_touch correctly", () => {
      expect(getInterventionTypeLabel("human_touch")).toBe("Human-Touch Retention Call");
    });
    it("maps human-touch (kebab) correctly", () => {
      expect(getInterventionTypeLabel("human-touch")).toBe("Human-Touch Retention Call");
    });
    it("returns em dash for null", () => {
      expect(getInterventionTypeLabel(null)).toBe("—");
    });
  });

  describe("getRetentionStrategyLabel", () => {
    it("maps onboard correctly", () => {
      expect(getRetentionStrategyLabel("onboard")).toBe("Onboarding Programme");
    });
    it("maps save correctly", () => {
      expect(getRetentionStrategyLabel("save")).toBe("Win-Back Save Attempt");
    });
    it("returns em dash for null", () => {
      expect(getRetentionStrategyLabel(null)).toBe("—");
    });
  });

  describe("getEngagementLevelLabel", () => {
    it("maps high correctly", () => {
      expect(getEngagementLevelLabel("high")).toBe("High Engagement");
    });
    it("maps none correctly", () => {
      expect(getEngagementLevelLabel("none")).toBe("No Engagement");
    });
    it("returns em dash for null", () => {
      expect(getEngagementLevelLabel(null)).toBe("—");
    });
  });
});
