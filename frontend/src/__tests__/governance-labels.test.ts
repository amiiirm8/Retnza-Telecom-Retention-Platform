import {
  getSchemaInfo,
  getPolicyRoleLabel,
  getCalibrationMethodLabel,
  getCompatibilityLabel,
  getFreshnessLevel,
  getMissingMetricReason,
  getPolicyIntendedUse,
  getPolicyBusinessInterpretation,
  getCvMethodLabel,
  getPolicyExplanation,
} from "@/lib/governance-labels";

describe("Governance Labels", () => {
  describe("getSchemaInfo", () => {
    it("returns info for known schema ID", () => {
      const info = getSchemaInfo("feature-schema");
      expect(info.friendlyName).toBe("Customer Signal Framework");
      expect(info.technicalId).toBe("feature-schema");
    });

    it("resolves legacy schema alias", () => {
      const info = getSchemaInfo("task4-v2");
      expect(info.friendlyName).toBe("Customer Signal Framework");
      expect(info.technicalId).toBe("feature-schema");
    });

    it("returns fallback for unknown schema ID", () => {
      const info = getSchemaInfo("unknown-schema");
      expect(info.technicalId).toBe("unknown-schema");
      expect(info.friendlyName).toBeTruthy();
    });

    it("returns fallback for null", () => {
      const info = getSchemaInfo(null);
      expect(info.friendlyName).toBe("—");
    });

    it("returns fallback for undefined", () => {
      const info = getSchemaInfo(undefined);
      expect(info.friendlyName).toBe("—");
    });

    it("returns info for production-champion-bundle", () => {
      const info = getSchemaInfo("production-champion-bundle");
      expect(info.friendlyName).toContain("Intelligence");
      expect(info.governanceRole).toBeTruthy();
    });

    it("resolves legacy champion-bundle-v4 alias", () => {
      const info = getSchemaInfo("champion-bundle-v4");
      expect(info.friendlyName).toContain("Intelligence");
      expect(info.governanceRole).toBeTruthy();
    });
  });

  describe("getPolicyRoleLabel", () => {
    it("labels primary_operating_policy", () => {
      expect(getPolicyRoleLabel("primary_operating_policy")).toContain("Primary");
    });
    it("labels reference_baseline", () => {
      expect(getPolicyRoleLabel("reference_baseline")).toContain("Baseline");
    });
    it("returns em dash for null", () => {
      expect(getPolicyRoleLabel(null)).toBe("—");
    });
    it("humanizes unknown role", () => {
      expect(getPolicyRoleLabel("custom_role")).toBe("Custom Role");
    });
    it("labels contact_budget_proxy", () => {
      expect(getPolicyRoleLabel("contact_budget_proxy")).toContain("Capacity");
    });
  });

  describe("getCalibrationMethodLabel", () => {
    it("labels isotonic", () => {
      expect(getCalibrationMethodLabel("isotonic")).toBe("Isotonic");
    });
    it("labels sigmoid", () => {
      expect(getCalibrationMethodLabel("sigmoid")).toContain("Sigmoid");
    });
    it("labels none", () => {
      expect(getCalibrationMethodLabel("none")).toContain("None");
    });
    it("returns em dash for null", () => {
      expect(getCalibrationMethodLabel(null)).toBe("—");
    });
    it("handles case insensitivity", () => {
      expect(getCalibrationMethodLabel("ISOTONIC")).toBe("Isotonic");
    });
  });

  describe("getCompatibilityLabel", () => {
    it("returns Compatible for compatible", () => {
      expect(getCompatibilityLabel("compatible")).toBe("Compatible");
    });
    it("returns Incompatible for incompatible", () => {
      expect(getCompatibilityLabel("incompatible")).toBe("Incompatible");
    });
    it("returns Unknown for null", () => {
      expect(getCompatibilityLabel(null)).toBe("Unknown");
    });
    it("returns Unknown for undefined", () => {
      expect(getCompatibilityLabel(undefined)).toBe("Unknown");
    });
    it("passes through unknown status", () => {
      expect(getCompatibilityLabel("custom")).toBe("custom");
    });
  });

  describe("getFreshnessLevel", () => {
    it("returns stale for null", () => {
      const f = getFreshnessLevel(null);
      expect(f.level).toBe("stale");
      expect(f.label).toBe("Unknown");
    });

    it("returns fresh for recent timestamp", () => {
      const f = getFreshnessLevel(new Date().toISOString());
      expect(f.level).toBe("fresh");
    });

    it("returns stale for invalid timestamp", () => {
      const f = getFreshnessLevel("not-a-date");
      expect(f.level).toBe("stale");
      expect(f.hours).toBe(Infinity);
    });

    it("returns stale for very old timestamp", () => {
      const f = getFreshnessLevel("2020-01-01T00:00:00Z");
      expect(f.level).toBe("stale");
    });
  });

  describe("getMissingMetricReason", () => {
    it("returns reason for reference_baseline", () => {
      const r = getMissingMetricReason("reference_baseline");
      expect(r).toContain("baseline");
    });
    it("returns default for null", () => {
      const r = getMissingMetricReason(null);
      expect(r).toContain("governance");
    });
    it("returns default for unknown role", () => {
      const r = getMissingMetricReason("unknown_role");
      expect(r).toContain("governance");
    });
  });

  describe("getPolicyIntendedUse", () => {
    it("returns use for primary_operating_policy", () => {
      expect(getPolicyIntendedUse("primary_operating_policy")).toBeTruthy();
    });
    it("returns empty for null", () => {
      expect(getPolicyIntendedUse(null)).toBe("");
    });
  });

  describe("getPolicyBusinessInterpretation", () => {
    it("returns interpretation for primary_operating_policy", () => {
      const i = getPolicyBusinessInterpretation("primary_operating_policy");
      expect(i).toContain("retention");
    });
    it("returns empty for null", () => {
      expect(getPolicyBusinessInterpretation(null)).toBe("");
    });
  });

  describe("getPolicyExplanation", () => {
    it("returns explanation for primary_operating_policy", () => {
      const e = getPolicyExplanation("primary_operating_policy");
      expect(e).toContain("churners");
    });
    it("returns empty for null", () => {
      expect(getPolicyExplanation(null)).toBe("");
    });
  });

  describe("getCvMethodLabel", () => {
    it("labels repeated_stratified_kfold", () => {
      const l = getCvMethodLabel("repeated_stratified_kfold");
      expect(l).toContain("Repeated");
    });
    it("returns em dash for null", () => {
      expect(getCvMethodLabel(null)).toBe("—");
    });
    it("humanizes unknown method", () => {
      const l = getCvMethodLabel("custom_method");
      expect(l).toBe("Custom Method");
    });
  });
});
