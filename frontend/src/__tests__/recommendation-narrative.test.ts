import { buildRecommendationNarrative } from "@/lib/recommendation-narrative";

describe("Recommendation Narrative", () => {
  it("builds narrative for known rule ID", () => {
    const n = buildRecommendationNarrative("R05_BILL_SHOCK", "incentivize");
    expect(n.businessName).toBe("Bill Shock Vulnerability");
    expect(n.technicalRuleId).toBe("R05_BILL_SHOCK");
    expect(n.fullActionText).toContain("incentive");
    expect(n.targetSegment).toContain("bill increase");
    expect(n.suggestedChannels.length).toBeGreaterThan(0);
    expect(n.playbookOffers.length).toBeGreaterThan(0);
  });

  it("returns fallback for unknown rule ID", () => {
    const n = buildRecommendationNarrative("R99_UNKNOWN", "incentivize");
    expect(n.businessName).toBe("Retention Play");
    expect(n.technicalRuleId).toBe("R99_UNKNOWN");
    expect(n.targetSegment).toBe("General subscriber base");
  });

  it("handles null rule ID", () => {
    const n = buildRecommendationNarrative(null, null);
    expect(n.businessName).toBe("—");
    expect(n.technicalRuleId).toBe("—");
    expect(n.fullActionText).toBe("—");
  });

  it("handles undefined rule ID", () => {
    const n = buildRecommendationNarrative(undefined, undefined);
    expect(n.businessName).toBe("—");
    expect(n.technicalRuleId).toBe("—");
  });

  it("sets urgencyLabel for immediate rules", () => {
    const n = buildRecommendationNarrative("R05_BILL_SHOCK", "incentivize");
    expect(n.urgencyLabel).toContain("24 hours");
  });

  it("sets interventionLabel for human-touch rules", () => {
    const n = buildRecommendationNarrative("R04_POSTPAID_5G", "escalate");
    expect(n.interventionLabel).toContain("Human-touch");
  });

  it("includes operational guidance for known rules", () => {
    const n = buildRecommendationNarrative("R05_BILL_SHOCK", "incentivize");
    expect(n.operationalGuidance.length).toBeGreaterThan(10);
    expect(n.operationalGuidance).toContain("bill explanation");
  });

  it("includes success signal for known rules", () => {
    const n = buildRecommendationNarrative("R05_BILL_SHOCK", "incentivize");
    expect(n.successSignal).toContain("usage alerts");
  });

  it("produces playbook offers for known rules", () => {
    const n = buildRecommendationNarrative("R01_PREPAID_INFANT", null);
    expect(n.playbookOffers.length).toBeGreaterThanOrEqual(2);
    expect(n.playbookOffers[0].title).toBeDefined();
    expect(n.playbookOffers[0].channel).toBeDefined();
  });

  it("builds narrative for all registered rule IDs without throwing", () => {
    const ids = [
      "R00_MONITOR", "R01_PREPAID_INFANT", "R02_PREPAID_5G",
      "R03_POSTPAID_INFANT", "R03_VOLTE_ENABLE", "R04_POSTPAID_5G",
      "R05_BILL_SHOCK", "R06_VOLTE_INACTIVE", "R06_VAS_PARTIAL",
      "R07_LEGACY_2G", "R08_LEGACY_3G", "R08_POSTPAID_EARLY",
      "R09_RUBIKA_INACTIVE", "R10_EWANO_NON_ADOPTER",
      "R11_HAMRAHMAN_LOW_ENGAGEMENT", "R12_ECOSYSTEM_POWER_USER",
      "R13_LEGACY_2G_ECO_DISENGAGED",
    ];
    ids.forEach((id) => {
      const n = buildRecommendationNarrative(id, null);
      expect(n.businessName).toBeTruthy();
      expect(n.technicalRuleId).toBe(id);
    });
  });
});
