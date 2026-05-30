"use client";

import { useState } from "react";
import { Card, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { RecommendationNarrative } from "@/lib/recommendation-narrative";

interface NarrativeCardProps {
  narrative: RecommendationNarrative;
  className?: string;
}

export function NarrativeCard({ narrative, className }: NarrativeCardProps) {
  const [showTech, setShowTech] = useState(false);

  return (
    <Card className={cn("space-y-4", className)}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <CardTitle>Retention Play</CardTitle>
          <h4 className="mt-1 text-lg font-bold text-slate-900">{narrative.businessName}</h4>
        </div>
        <button
          onClick={() => setShowTech(!showTech)}
          className="shrink-0 rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-medium text-slate-500 transition-colors hover:bg-slate-200"
        >
          {showTech ? "Hide ID" : "Show ID"}
        </button>
      </div>

      {showTech && (
        <div className="rounded-lg bg-slate-50 p-3 font-mono text-xs text-slate-400">
          Technical ID: {narrative.technicalRuleId}
        </div>
      )}

      <p className="text-sm leading-relaxed text-slate-700">{narrative.executiveSummary}</p>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg bg-indigo-50 p-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-indigo-600">Target Segment</p>
          <p className="mt-1 text-sm font-medium text-slate-800">{narrative.targetSegment}</p>
        </div>
        <div className="rounded-lg bg-emerald-50 p-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-emerald-600">Objective</p>
          <p className="mt-1 text-sm font-medium text-slate-800">{narrative.retentionObjective}</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <span className="inline-flex items-center rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-medium text-amber-700">
          {narrative.urgencyLabel}
        </span>
        <span className="inline-flex items-center rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-medium text-blue-700">
          {narrative.interventionLabel}
        </span>
        <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600">
          {narrative.estimatedComplexityLabel}
        </span>
      </div>

      {narrative.suggestedChannels.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Suggested Channels</p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {narrative.suggestedChannels.map((ch) => (
              <span
                key={ch}
                className="inline-flex items-center rounded-md border border-slate-200 bg-white px-2 py-0.5 text-xs text-slate-600"
              >
                {ch}
              </span>
            ))}
          </div>
        </div>
      )}

      <div>
        <p className="text-sm font-medium text-slate-700">Action</p>
        <p className="mt-0.5 text-sm leading-snug text-slate-600">{narrative.fullActionText}</p>
      </div>

      {narrative.playbookOffers.length > 0 && (
        <div>
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            Telecom Offers / Playbook
          </p>
          <div className="space-y-2">
            {narrative.playbookOffers.map((offer, i) => (
              <div key={i} className="rounded-lg border border-slate-200 bg-white p-3">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-medium text-slate-800">{offer.title}</p>
                  <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">
                    {offer.channel}
                  </span>
                </div>
                <p className="mt-0.5 text-xs text-slate-500">{offer.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Operational Guidance</p>
        <p className="mt-1 text-xs leading-relaxed text-slate-600">{narrative.operationalGuidance}</p>
      </div>

      <div>
        <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Success Signal</p>
        <p className="mt-0.5 text-xs text-slate-500">{narrative.successSignal}</p>
      </div>
    </Card>
  );
}
