/**
 * Retention Play Catalog & Decision Contract Registry
 *
 * Formal catalog of all deterministic retention plays (R00–R13) that
 * constitute the system's recommendation engine. Each play is a structured
 * decision contract defining:
 *
 * - Target subscriber segment (who this applies to)
 * - Retention objective (what we want to achieve)
 * - Operational urgency (when to act)
 * - Intervention type (how to reach the subscriber)
 * - Playbook offers (specific telecom retention treatments)
 * - Operational guidance (CRM team instructions)
 * - Success signal (how to measure effectiveness)
 *
 * Key architectural principle: SHAP explainability provides narrative context
 * for WHY a subscriber was flagged, but the retention ACTION is determined
 * by these deterministic rules — not by the ML model. This ensures:
 * - Actions are auditable and explainable
 * - Rules are testable and version-controlled
 * - CRM teams understand exactly why each action was recommended
 * - No hidden ML logic drives retention decisions
 */

/**
 * A single playbook offer within a retention recommendation.
 * Each offer pairs a human-readable title with a channel-specific description
 * that CRM agents can act on directly.
 */
export interface PlaybookOffer {
  /** Offer headline for agent-facing UI */
  title: string;
  /** Actionable description including incentive details and timing */
  description: string;
  /** Delivery channel (e.g. SMS, Push Notification, Call Center) */
  channel: string;
}

/**
 * Formal decision contract for a deterministic retention play (R00–R13).
 * Each entry fully specifies the who, what, when, how, and success criteria
 * for a single retention play, independent of ML model scores.
 */
export interface RecommendationCatalogEntry {
  id: string;
  businessName: string;
  executiveSummary: string;
  targetSegment: string;
  retentionObjective: string;
  suggestedChannels: string[];
  urgency: "immediate" | "short-term" | "planned";
  interventionType: "digital" | "human-touch" | "hybrid";
  playbookOffers: PlaybookOffer[];
  operationalGuidance: string;
  successSignal: string;
  estimatedComplexity: "low" | "medium" | "high";
}

/**
 * Complete catalog of deterministic retention plays.
 * Each entry is a fully specified decision contract.
 * Rules are triggered by subscriber attribute patterns, not by raw ML scores.
 */
export const RECOMMENDATION_CATALOG: Record<string, RecommendationCatalogEntry> = {
  R00_MONITOR: {
    id: "R00_MONITOR",
    businessName: "Monitor Emerging Risk",
    executiveSummary:
      "Subscriber exhibits mild early churn indicators requiring observation rather than immediate intervention. Low-touch engagement is appropriate unless risk signals escalate in the next scoring cycle.",
    targetSegment: "Subscribers with below-threshold churn probability but emerging behavioural signals",
    retentionObjective: "Monitor and maintain engagement through low-touch retention tactics",
    suggestedChannels: ["SMS", "Push Notification"],
    urgency: "planned",
    interventionType: "digital",
    playbookOffers: [
      {
        title: "Check-In Message",
        description: "Friendly SMS check-in with personalised usage summary and support offer",
        channel: "SMS",
      },
      {
        title: "Value-Add Highlight",
        description: "Push notification showcasing relevant but unused service benefits",
        channel: "Push Notification",
      },
    ],
    operationalGuidance:
      "Suppress from intensive retention campaigns. Apply low-priority digital-only treatment. Reassess at next scoring cycle.",
    successSignal:
      "Subscriber returns to stable risk tier without requiring escalation",
    estimatedComplexity: "low",
  },

  R01_PREPAID_INFANT: {
    id: "R01_PREPAID_INFANT",
    businessName: "New Prepaid User Risk",
    executiveSummary:
      "Subscriber is in the early prepaid lifecycle with limited tenure and low engagement. Early intervention through onboarding and first-time recharge incentives can stabilise the relationship before disengagement patterns form.",
    targetSegment: "Prepaid subscribers with less than 3 months tenure",
    retentionObjective: "Drive first-month engagement and establish recurring recharge habit",
    suggestedChannels: ["SMS", "Push Notification", "In-App"],
    urgency: "immediate",
    interventionType: "digital",
    playbookOffers: [
      {
        title: "Welcome Bonus",
        description: "One-time bonus data or voice bundle on first recharge within 7 days",
        channel: "SMS",
      },
      {
        title: "Onboarding Journey",
        description: "5-day SMS sequence: welcome → product highlights → first recharge offer → tips → reward",
        channel: "SMS",
      },
      {
        title: "Low-Cost Starter Pack",
        description: "Discounted 7-day internet+voice starter pack available via USSD",
        channel: "Push Notification",
      },
    ],
    operationalGuidance:
      "Trigger welcome SMS within 24 hours of rule detection. If no recharge within 3 days, escalate to push notification. Priority: P2 unless churn probability exceeds threshold.",
    successSignal:
      "Subscriber completes first recharge within 7 days or engages with onboarding content",
    estimatedComplexity: "low",
  },

  R02_PREPAID_5G: {
    id: "R02_PREPAID_5G",
    businessName: "5G Prepaid Churn Exposure",
    executiveSummary:
      "Subscriber is a prepaid 5G-capable user showing early behavioural churn signals. Without targeted 5G value reinforcement, this segment risks switching to a competing 5G network.",
    targetSegment: "Prepaid 5G-capable subscribers with declining data usage",
    retentionObjective: "Reinforce 5G value proposition and increase data consumption",
    suggestedChannels: ["Push Notification", "In-App", "SMS"],
    urgency: "immediate",
    interventionType: "digital",
    playbookOffers: [
      {
        title: "5G Speed Boost Trial",
        description: "Free 3-day 5G speed upgrade with promotional data bonus",
        channel: "Push Notification",
      },
      {
        title: "5G Content Bundle",
        description: "Discounted streaming + social media data pack for 5G users",
        channel: "In-App",
      },
      {
        title: "Network Experience Survey",
        description: "Short feedback survey with bonus data reward on completion",
        channel: "SMS",
      },
    ],
    operationalGuidance:
      "Verify device is 5G-capable and currently on 4G. Push notification with speed trial offer is first-line treatment. Monitor data usage uplift within 7 days.",
    successSignal:
      "Data usage increases by 20%+ within 14 days or subscriber moves to 5G data plan",
    estimatedComplexity: "low",
  },

  R03_POSTPAID_INFANT: {
    id: "R03_POSTPAID_INFANT",
    businessName: "New Postpaid User Risk",
    executiveSummary:
      "Subscriber is in the early postpaid lifecycle. Postpaid churn is highest in the first 90 days. Structured onboarding and first-bill transparency reduce early churn risk.",
    targetSegment: "Postpaid subscribers with less than 90 days tenure",
    retentionObjective: "Complete onboarding and establish payment confidence",
    suggestedChannels: ["Call Center", "SMS", "Email"],
    urgency: "short-term",
    interventionType: "hybrid",
    playbookOffers: [
      {
        title: "Postpaid Welcome Call",
        description: "Outbound welcome call explaining bill structure, usage tracking, and value-added services",
        channel: "Call Center",
      },
      {
        title: "First-Bill Alert",
        description: "SMS and email notification before first bill generation with breakdown preview",
        channel: "SMS",
      },
      {
        title: "Loyalty Points Boost",
        description: "Double loyalty points on first 3 bills to incentivise payment and retention",
        channel: "Email",
      },
    ],
    operationalGuidance:
      "Schedule welcome call within 48 hours of activation. Send bill preview 5 days before first bill. Flag if first bill exceeds 80% of committed amount for soft retention call.",
    successSignal:
      "Subscriber pays first two bills on time and engages with welcome call",
    estimatedComplexity: "medium",
  },

  R03_VOLTE_ENABLE: {
    id: "R03_VOLTE_ENABLE",
    businessName: "VoLTE Migration Opportunity",
    executiveSummary:
      "Subscriber has VoLTE-capable device but has not adopted VoLTE services. VoLTE usage is associated with lower observed churn risk and improved service quality.",
    targetSegment: "VoLTE-capable subscribers not using VoLTE",
    retentionObjective: "Drive VoLTE activation to strengthen network attachment",
    suggestedChannels: ["SMS", "Push Notification", "USSD"],
    urgency: "short-term",
    interventionType: "digital",
    playbookOffers: [
      {
        title: "VoLTE Activation Guide",
        description: "Free activation support via SMS with one-click enablement link",
        channel: "SMS",
      },
      {
        title: "VoLTE Bonus Data",
        description: "1GB free data on successful VoLTE activation — valid for 7 days",
        channel: "Push Notification",
      },
      {
        title: "HD Voice Trial",
        description: "30-day HD voice trial with no additional charges",
        channel: "USSD",
      },
    ],
    operationalGuidance:
      "Verify device capability from handset data. Send activation guide via SMS. Follow up with bonus offer after 72 hours if still inactive.",
    successSignal:
      "VoLTE becomes active within 14 days of outreach",
    estimatedComplexity: "low",
  },

  R04_POSTPAID_5G: {
    id: "R04_POSTPAID_5G",
    businessName: "5G Postpaid Churn Exposure",
    executiveSummary:
      "High-value postpaid 5G subscriber showing elevated churn signals. Competitive risk from alternative 5G offerings. Requires premium retention treatment to protect revenue.",
    targetSegment: "Postpaid 5G subscribers with above-average monthly spend",
    retentionObjective: "Secure mid-term contract commitment and increase 5G service attachment",
    suggestedChannels: ["Call Center", "In-App", "Email"],
    urgency: "immediate",
    interventionType: "human-touch",
    playbookOffers: [
      {
        title: "Exclusive 5G Plan Upgrade",
        description: "Discounted upgrade to premium 5G plan with unlimited streaming and priority support",
        channel: "Call Center",
      },
      {
        title: "Device Upgrade Programme",
        description: "Early device upgrade eligibility with 5G handset subsidy",
        channel: "In-App",
      },
      {
        title: "VIP Care Package",
        description: "Dedicated relationship manager, priority call routing, and exclusive event invitations",
        channel: "Call Center",
      },
    ],
    operationalGuidance:
      "Assign to high-value retention team. Outbound call within 24 hours. Offer personalised plan based on usage patterns. Do not apply standard digital-only treatment.",
    successSignal:
      "Subscriber accepts plan upgrade or VIP care package; churn probability does not increase",
    estimatedComplexity: "high",
  },

  R05_BILL_SHOCK: {
    id: "R05_BILL_SHOCK",
    businessName: "Bill Shock Vulnerability",
    executiveSummary:
      "Subscriber experienced a sudden bill increase above behavioural threshold. Bill shock is one of the strongest churn predictors in telecom. Immediate transparency and cost-control measures are required.",
    targetSegment: "Subscribers with bill increase exceeding 30% month-over-month",
    retentionObjective: "Restore billing confidence and provide cost-control tools",
    suggestedChannels: ["SMS", "Call Center", "In-App"],
    urgency: "immediate",
    interventionType: "digital",
    playbookOffers: [
      {
        title: "Bill Explanation",
        description: "Personalised SMS or in-app breakdown explaining the increase with usage highlights",
        channel: "SMS",
      },
      {
        title: "Usage Alert Activation",
        description: "Free opt-in to real-time usage alerts for voice, data, and SMS",
        channel: "SMS",
      },
      {
        title: "Plan Optimisation",
        description: "Recommendation to switch to a better-fitting plan based on actual usage patterns",
        channel: "In-App",
      },
      {
        title: "Bill Credit / Goodwill",
        description: "One-time goodwill credit for loyal subscribers with clean payment history",
        channel: "Call Center",
      },
    ],
    operationalGuidance:
      "Send bill explanation within 2 hours of detection. Offer usage alerts immediately. If subscriber is high-value and bill increase >50%, trigger human-touch retention call.",
    successSignal:
      "Subscriber opts into usage alerts or adjusts plan; no second consecutive bill shock event",
    estimatedComplexity: "low",
  },

  R06_VOLTE_INACTIVE: {
    id: "R06_VOLTE_INACTIVE",
    businessName: "VoLTE Non-Adoption",
    executiveSummary:
      "Subscriber has a VoLTE-capable device but has not activated VoLTE. VoLTE adoption is associated with lower churn risk and improved network experience.",
    targetSegment: "VoLTE-capable subscribers with VoLTE inactive",
    retentionObjective: "Drive VoLTE activation to improve service quality and reduce churn",
    suggestedChannels: ["SMS", "Push Notification", "USSD"],
    urgency: "short-term",
    interventionType: "digital",
    playbookOffers: [
      {
        title: "VoLTE Activation Guide",
        description: "Step-by-step SMS guide to enable VoLTE with free setup support number",
        channel: "SMS",
      },
      {
        title: "VoLTE Bonus Data",
        description: "Free 1GB data on successful VoLTE activation, valid for 7 days",
        channel: "Push Notification",
      },
      {
        title: "HD Voice Trial",
        description: "30-day HD voice trial available via USSD activation code",
        channel: "USSD",
      },
    ],
    operationalGuidance:
      "Verify device VoLTE capability from handset data. Send activation guide via SMS. Follow up with bonus offer after 72 hours if still inactive.",
    successSignal:
      "VoLTE becomes active within 14 days of outreach",
    estimatedComplexity: "low",
  },

  R06_VAS_PARTIAL: {
    id: "R06_VAS_PARTIAL",
    businessName: "Low Service Engagement",
    executiveSummary:
      "Subscriber shows limited adoption of digital and value-added services. Weak ecosystem engagement is associated with higher observed churn risk. Low-touch digital onboarding to relevant services can improve retention.",
    targetSegment: "Subscribers with fewer than 2 active value-added or digital services",
    retentionObjective: "Increase value-added service adoption to strengthen ecosystem attachment",
    suggestedChannels: ["SMS", "Push Notification", "In-App"],
    urgency: "planned",
    interventionType: "digital",
    playbookOffers: [
      {
        title: "Service Discovery",
        description: "Personalised SMS showcasing 2-3 relevant services based on usage profile",
        channel: "SMS",
      },
      {
        title: "Free Trial Bundle",
        description: "7-day free access to a selection of digital services with auto-opt-out",
        channel: "Push Notification",
      },
      {
        title: "Starter Pack",
        description: "Discounted bundle of VAS services for first-time adopters",
        channel: "SMS",
      },
    ],
    operationalGuidance:
      "Profile subscriber to identify relevant services. Send personalised discovery SMS. Follow with free trial offer if no adoption within 14 days.",
    successSignal:
      "Subscriber activates at least one additional service within 30 days",
    estimatedComplexity: "low",
  },

  R07_LEGACY_2G: {
    id: "R07_LEGACY_2G",
    businessName: "Legacy Network Dependency (2G)",
    executiveSummary:
      "Subscriber is still on the 2G network with limited data usage. As 2G sunset approaches, these users need migration support to avoid service disruption and involuntary churn.",
    targetSegment: "2G-only subscribers with no 4G/5G device history",
    retentionObjective: "Migrate to 4G-capable device and plan before 2G decommissioning",
    suggestedChannels: ["Call Center", "SMS", "In-App"],
    urgency: "short-term",
    interventionType: "hybrid",
    playbookOffers: [
      {
        title: "Device Upgrade Subsidy",
        description: "Discounted 4G/5G handset with trade-in programme for legacy devices",
        channel: "Call Center",
      },
      {
        title: "Migration Plan",
        description: "Special 4G transition plan with 3 months of reduced-rate data",
        channel: "SMS",
      },
      {
        title: "Technology Awareness",
        description: "Educational content about 2G sunset timeline, device compatibility, and upgrade benefits",
        channel: "SMS",
      },
    ],
    operationalGuidance:
      "Segment by device upgrade history. High-value legacy subscribers receive outbound call. Low-value receive SMS campaign with device subsidy offer.",
    successSignal:
      "Subscriber upgrades to 4G device or transitions to 4G plan within 60 days",
    estimatedComplexity: "high",
  },

  R08_LEGACY_3G: {
    id: "R08_LEGACY_3G",
    businessName: "Legacy Network Dependency (3G)",
    executiveSummary:
      "Subscriber is still primarily on the 3G network. While 3G has more runway than 2G, migration to 4G/5G improves experience and reduces long-term churn risk.",
    targetSegment: "3G-dominant subscribers with limited 4G/5G usage",
    retentionObjective: "Accelerate migration to 4G/5G for improved experience and retention",
    suggestedChannels: ["SMS", "Push Notification", "In-App"],
    urgency: "planned",
    interventionType: "digital",
    playbookOffers: [
      {
        title: "4G Discovery Offer",
        description: "Free 7-day 4G speed trial with bonus data for 3G users who switch",
        channel: "SMS",
      },
      {
        title: "Plan Migration",
        description: "Same-price plan upgrade with 4G/5G data allowance increase",
        channel: "In-App",
      },
      {
        title: "Network Optimisation Tip",
        description: "Guide to enable 4G on device settings with free support",
        channel: "Push Notification",
      },
    ],
    operationalGuidance:
      "Target subscribers with 4G-capable devices still on 3G. Push digital offer first. Escalate to call centre if no migration within 30 days.",
    successSignal:
      "Subscriber moves from 3G-dominant to 4G/5G-dominant usage within 30 days",
    estimatedComplexity: "low",
  },

  R08_POSTPAID_EARLY: {
    id: "R08_POSTPAID_EARLY",
    businessName: "Early Lifecycle Postpaid Risk",
    executiveSummary:
      "Recently onboarded postpaid subscriber showing elevated early-tenure churn sensitivity. Early lifecycle intervention through structured onboarding, first-bill transparency, and loyalty programme enrolment can stabilise retention.",
    targetSegment: "Postpaid subscribers with less than 60 days tenure and elevated risk",
    retentionObjective: "Strengthen early postpaid relationship through structured onboarding and loyalty enrolment",
    suggestedChannels: ["Call Center", "SMS", "In-App"],
    urgency: "short-term",
    interventionType: "hybrid",
    playbookOffers: [
      {
        title: "Postpaid Welcome Journey",
        description: "3-step SMS onboarding: bill understanding, usage tracking setup, loyalty programme enrolment",
        channel: "SMS",
      },
      {
        title: "First-Bill Assurance",
        description: "Proactive SMS and email before first bill with personalised breakdown and payment options",
        channel: "SMS",
      },
      {
        title: "Loyalty Early Enrolment",
        description: "Automatic Hamrah Man enrolment with welcome points and tier-placement support",
        channel: "In-App",
      },
    ],
    operationalGuidance:
      "Trigger welcome SMS sequence within 24 hours of detection. Schedule outbound call if first bill exceeds 70% of plan commitment. Enrol in loyalty programme automatically.",
    successSignal:
      "Subscriber stays active through first 90 days and engages with loyalty programme",
    estimatedComplexity: "medium",
  },

  R09_RUBIKA_INACTIVE: {
    id: "R09_RUBIKA_INACTIVE",
    businessName: "Low Rubika Engagement",
    executiveSummary:
      "Subscriber has Rubika capability but shows low or declining engagement. Rubika-active users are associated with lower churn risk. Re-engagement through personalised content can restore activity.",
    targetSegment: "Rubika-capable subscribers with below-threshold engagement",
    retentionObjective: "Restore Rubika engagement to reduce churn risk",
    suggestedChannels: ["Push Notification", "In-App", "SMS"],
    urgency: "short-term",
    interventionType: "digital",
    playbookOffers: [
      {
        title: "Rubika Re-engagement",
        description: "Personalised push notification with trending content or missed messages",
        channel: "Push Notification",
      },
      {
        title: "Rubika Data Pack",
        description: "Free Rubika-specific data pack for 7 days to encourage usage",
        channel: "SMS",
      },
      {
        title: "Rubika Premium Trial",
        description: "14-day free trial of Rubika Premium with exclusive stickers and themes",
        channel: "In-App",
      },
    ],
    operationalGuidance:
      "Send push re-engagement notification immediately. If no activity within 48 hours, send SMS with free Rubika data pack offer. Monitor engagement weekly.",
    successSignal:
      "Subscriber opens Rubika at least once within 7 days of outreach",
    estimatedComplexity: "low",
  },

  R10_EWANO_NON_ADOPTER: {
    id: "R10_EWANO_NON_ADOPTER",
    businessName: "EWANO Non-Adoption",
    executiveSummary:
      "Subscriber is capable of using EWANO but has not activated the service. EWANO adoption expands the subscriber's ecosystem attachment and is associated with lower churn.",
    targetSegment: "EWANO-capable subscribers who have not activated",
    retentionObjective: "Drive first-time EWANO activation and initial transaction",
    suggestedChannels: ["SMS", "Push Notification", "USSD"],
    urgency: "short-term",
    interventionType: "digital",
    playbookOffers: [
      {
        title: "EWANO Welcome",
        description: "SMS with activation link and 50,000 Rial first-transaction bonus",
        channel: "SMS",
      },
      {
        title: "EWANO Cashback Campaign",
        description: "10% cashback on first 3 transactions within 14 days of activation",
        channel: "Push Notification",
      },
      {
        title: "EWANO Merchant Discovery",
        description: "Curated list of nearby EWANO merchants with special offers",
        channel: "USSD",
      },
    ],
    operationalGuidance:
      "Send activation SMS with bonus offer. Follow up with push notification after 7 days if not activated. If still inactive after 14 days, suppress and reassess.",
    successSignal:
      "Subscriber activates EWANO and completes at least one transaction within 14 days",
    estimatedComplexity: "low",
  },

  R11_HAMRAHMAN_LOW_ENGAGEMENT: {
    id: "R11_HAMRAHMAN_LOW_ENGAGEMENT",
    businessName: "Low Hamrah Man Engagement",
    executiveSummary:
      "Subscriber is enrolled in Hamrah Man but engagement has dropped below threshold. Hamrah Man is the operator's loyalty platform; low engagement signals weakening brand attachment.",
    targetSegment: "Hamrah Man members with below-threshold engagement score",
    retentionObjective: "Increase Hamrah Man engagement to strengthen loyalty and reduce churn",
    suggestedChannels: ["In-App", "Push Notification", "SMS"],
    urgency: "short-term",
    interventionType: "digital",
    playbookOffers: [
      {
        title: "Points Boost Event",
        description: "Double points on all activities for the next 7 days with personalised challenges",
        channel: "In-App",
      },
      {
        title: "Loyalty Tier Upgrade Path",
        description: "Clear roadmap showing required points for next tier with personalised targets",
        channel: "Push Notification",
      },
      {
        title: "Exclusive Reward Voucher",
        description: "Redeemable voucher for data, voice, or ecosystem services based on engagement level",
        channel: "SMS",
      },
    ],
    operationalGuidance:
      "Target subscribers who have not engaged with Hamrah Man in >30 days. Push notification with points boost is first line. Follow with SMS reward voucher if no engagement within 5 days.",
    successSignal:
      "Subscriber completes at least one Hamrah Man action within 7 days of campaign",
    estimatedComplexity: "medium",
  },

  R12_ECOSYSTEM_POWER_USER: {
    id: "R12_ECOSYSTEM_POWER_USER",
    businessName: "High Loyalty Ecosystem Users",
    executiveSummary:
      "High-value multi-product ecosystem user. While these subscribers have lower observed churn risk, their high lifetime value makes them priority candidates for premium retention and win-back programmes.",
    targetSegment: "Multi-product ecosystem users with high engagement scores",
    retentionObjective: "Protect high-LTV subscribers through exclusive benefits and proactive outreach",
    suggestedChannels: ["Call Center", "In-App", "Email"],
    urgency: "planned",
    interventionType: "human-touch",
    playbookOffers: [
      {
        title: "Loyalty Concierge",
        description: "Dedicated retention agent for personalised plan recommendations and priority issue resolution",
        channel: "Call Center",
      },
      {
        title: "Ecosystem Bundle Discount",
        description: "Multi-product discount for subscribers with 3+ ecosystem products",
        channel: "In-App",
      },
      {
        title: "Early Access Programme",
        description: "Beta access to new services, products, and feature releases before general availability",
        channel: "Email",
      },
    ],
    operationalGuidance:
      "Flag for VIP retention team. Do not apply standard digital treatments. Quarterly check-in calls recommended. Offer personalised bundle discount based on product mix.",
    successSignal:
      "Subscriber maintains or increases ecosystem product count; no escalation to churn",
    estimatedComplexity: "medium",
  },

  R13_LEGACY_2G_ECO_DISENGAGED: {
    id: "R13_LEGACY_2G_ECO_DISENGAGED",
    businessName: "Legacy User — Ecosystem Disengaged",
    executiveSummary:
      "Subscriber is on legacy 2G network and not engaged with any ecosystem product. This dual-exclusion group faces the highest observed risk. Requires coordinated network migration and ecosystem onboarding.",
    targetSegment: "2G legacy users not engaged with Rubika, EWANO, Hamrah Man, or VoLTE",
    retentionObjective: "Dual-path intervention: network upgrade + ecosystem first-product adoption",
    suggestedChannels: ["Call Center", "SMS", "In-App"],
    urgency: "short-term",
    interventionType: "hybrid",
    playbookOffers: [
      {
        title: "Combined Device + Ecosystem Offer",
        description: "Subsidised 4G handset with preloaded Rubika and EWANO activation",
        channel: "Call Center",
      },
      {
        title: "Ecosystem Starter Pack",
        description: "30-day free access to Rubika, EWANO, and Hamrah Man with onboarding support",
        channel: "SMS",
      },
      {
        title: "Legacy Migration Support",
        description: "End-to-end migration assistance including device setup, number porting, and ecosystem activation",
        channel: "Call Center",
      },
    ],
    operationalGuidance:
      "High-priority segment. Outbound call within 48 hours. Offer combined device subsidy + ecosystem starter. Track both network migration and first ecosystem product activation as success metrics.",
    successSignal:
      "Subscriber migrates to 4G and activates at least one ecosystem product within 60 days",
    estimatedComplexity: "high",
  },
};

/**
 * Looks up a catalog entry by rule ID.
 * Returns null for unknown/unregistered rule IDs rather than throwing,
 * since the catalog may be updated asynchronously from the rule engine.
 */
export function getCatalogEntry(ruleId: string | null | undefined): RecommendationCatalogEntry | null {
  if (!ruleId) return null;
  return RECOMMENDATION_CATALOG[ruleId] || null;
}

/**
 * Returns the playbook offers array for a given rule ID.
 * Returns an empty array for unknown rules so callers can safely map over results.
 */
export function getPlaybookOffers(ruleId: string | null | undefined): PlaybookOffer[] {
  return getCatalogEntry(ruleId)?.playbookOffers || [];
}
