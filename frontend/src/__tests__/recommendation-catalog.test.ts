import { getCatalogEntry, getPlaybookOffers, RECOMMENDATION_CATALOG } from "@/lib/recommendation-catalog";

describe("Recommendation Catalog", () => {
  describe("getCatalogEntry", () => {
    it("returns entry for R05_BILL_SHOCK", () => {
      const entry = getCatalogEntry("R05_BILL_SHOCK");
      expect(entry).toBeDefined();
      expect(entry!.businessName).toBe("Bill Shock Vulnerability");
      expect(entry!.urgency).toBe("immediate");
      expect(entry!.interventionType).toBe("digital");
    });

    it("returns null for undefined", () => {
      expect(getCatalogEntry(undefined)).toBeNull();
    });

    it("returns null for null", () => {
      expect(getCatalogEntry(null)).toBeNull();
    });

    it("returns null for empty string", () => {
      expect(getCatalogEntry("")).toBeNull();
    });

    it("returns null for unknown ID", () => {
      expect(getCatalogEntry("UNKNOWN_RULE")).toBeNull();
    });
  });

  describe("getPlaybookOffers", () => {
    it("returns offers for R05_BILL_SHOCK", () => {
      const offers = getPlaybookOffers("R05_BILL_SHOCK");
      expect(offers.length).toBeGreaterThan(0);
      expect(offers[0].title).toBeDefined();
      expect(offers[0].channel).toBeDefined();
    });

    it("returns empty array for null", () => {
      expect(getPlaybookOffers(null)).toEqual([]);
    });

    it("returns empty array for unknown rule", () => {
      expect(getPlaybookOffers("UNKNOWN")).toEqual([]);
    });
  });

  describe("Catalog completeness", () => {
    it("all entries have required fields", () => {
      const entries = Object.values(RECOMMENDATION_CATALOG);
      entries.forEach((entry) => {
        expect(entry.id).toBeTruthy();
        expect(entry.businessName).toBeTruthy();
        expect(entry.executiveSummary).toBeTruthy();
        expect(entry.targetSegment).toBeTruthy();
        expect(entry.retentionObjective).toBeTruthy();
        expect(entry.suggestedChannels.length).toBeGreaterThan(0);
        expect(["immediate", "short-term", "planned"]).toContain(entry.urgency);
        expect(["digital", "human-touch", "hybrid"]).toContain(entry.interventionType);
        expect(entry.operationalGuidance).toBeTruthy();
        expect(entry.successSignal).toBeTruthy();
        expect(["low", "medium", "high"]).toContain(entry.estimatedComplexity);
      });
    });

    it("all catalog IDs match their keys", () => {
      Object.entries(RECOMMENDATION_CATALOG).forEach(([key, entry]) => {
        expect(entry.id).toBe(key);
      });
    });
  });
});
