import { formatNumber, formatPercent, formatDecimal, toPersianDigits } from "@/lib/format";

describe("Format Utilities", () => {
  describe("formatNumber", () => {
    it("formats with English locale", () => {
      expect(formatNumber(1234567, "en")).toBe("1,234,567");
    });
    it("returns em dash for null", () => {
      expect(formatNumber(null, "en")).toBe("—");
    });
    it("returns em dash for undefined", () => {
      expect(formatNumber(undefined, "en")).toBe("—");
    });
    it("formats zero correctly", () => {
      expect(formatNumber(0, "en")).toBe("0");
    });
  });

  describe("formatPercent", () => {
    it("formats 0-1 ratio as percentage", () => {
      expect(formatPercent(0.073, "en")).toBe("7.3%");
    });
    it("returns em dash for null", () => {
      expect(formatPercent(null, "en")).toBe("—");
    });
    it("handles zero", () => {
      expect(formatPercent(0, "en")).toBe("0.0%");
    });
    it("handles 1.0 (100%)", () => {
      expect(formatPercent(1, "en")).toBe("100.0%");
    });
  });

  describe("formatDecimal", () => {
    it("formats to default 3 decimals", () => {
      expect(formatDecimal(0.1234, "en")).toBe("0.123");
    });
    it("formats to custom decimals", () => {
      expect(formatDecimal(0.12345, "en", 4)).toBe("0.1235");
    });
    it("returns em dash for null", () => {
      expect(formatDecimal(null, "en")).toBe("—");
    });
  });

  describe("toPersianDigits", () => {
    it("converts digits to Persian", () => {
      expect(toPersianDigits("123")).toBe("۱۲۳");
    });
    it("passes through non-digit characters", () => {
      expect(toPersianDigits("7.3%")).toBe("۷.۳%");
    });
    it("handles numeric input", () => {
      expect(toPersianDigits(456)).toBe("۴۵۶");
    });
  });
});
