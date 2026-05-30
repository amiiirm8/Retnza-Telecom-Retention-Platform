import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import { ExecutiveRiskBadge, PriorityBadge, CompatBadge, Badge } from "@/components/ui/badge";

describe("ExecutiveRiskBadge", () => {
  it("renders Critical for Very High tier", () => {
    render(<ExecutiveRiskBadge tier="Very High" />);
    expect(screen.getByText("Critical")).toBeInTheDocument();
  });

  it("renders At Risk for High tier", () => {
    render(<ExecutiveRiskBadge tier="High" />);
    expect(screen.getByText("At Risk")).toBeInTheDocument();
  });

  it("renders Watchlist for Medium tier", () => {
    render(<ExecutiveRiskBadge tier="Medium" />);
    expect(screen.getByText("Watchlist")).toBeInTheDocument();
  });

  it("renders Stable for Low tier", () => {
    render(<ExecutiveRiskBadge tier="Low" />);
    expect(screen.getByText("Stable")).toBeInTheDocument();
  });

  it("returns null for null tier", () => {
    const { container } = render(<ExecutiveRiskBadge tier={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("shows technical tier when showTechnical is true", () => {
    render(<ExecutiveRiskBadge tier="Very High" showTechnical />);
    expect(screen.getByText(/\(Very High\)/)).toBeInTheDocument();
  });
});

describe("PriorityBadge", () => {
  it("renders P1 badge", () => {
    render(<PriorityBadge priority="P1" />);
    expect(screen.getByText("P1")).toBeInTheDocument();
  });

  it("renders P2 badge", () => {
    render(<PriorityBadge priority="P2" />);
    expect(screen.getByText("P2")).toBeInTheDocument();
  });

  it("returns null for null priority", () => {
    const { container } = render(<PriorityBadge priority={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders P4 badge", () => {
    render(<PriorityBadge priority="P4" />);
    expect(screen.getByText("P4")).toBeInTheDocument();
  });
});

describe("CompatBadge", () => {
  it("renders compatible status", () => {
    render(<CompatBadge status="compatible" />);
    expect(screen.getByText("Compatible")).toBeInTheDocument();
  });

  it("renders incompatible status", () => {
    render(<CompatBadge status="incompatible" />);
    expect(screen.getByText("Incompatible")).toBeInTheDocument();
  });

  it("renders Unknown for null status", () => {
    render(<CompatBadge status={null} />);
    expect(screen.getByText("Unknown")).toBeInTheDocument();
  });

  it("renders Unknown for undefined status", () => {
    render(<CompatBadge status={undefined as unknown as null} />);
    expect(screen.getByText("Unknown")).toBeInTheDocument();
  });
});

describe("Badge", () => {
  it("renders children text", () => {
    render(<Badge>Test Badge</Badge>);
    expect(screen.getByText("Test Badge")).toBeInTheDocument();
  });

  it("applies variant classes", () => {
    render(<Badge variant="success">Success</Badge>);
    expect(screen.getByText("Success")).toBeInTheDocument();
  });
});
