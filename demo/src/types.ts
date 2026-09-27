export const DESIGN_DIRECTIONS = ["海报", "插画", "文创", "包装", "品牌/VI", "字体", "书籍装帧", "漫画", "标志", "IP/吉祥物", "信息图形", "综合视觉"] as const;
export type DesignDirection = (typeof DESIGN_DIRECTIONS)[number];

export type CompetitionWorkItem = {
    name: string;
    kind: "visual_design" | "product_concept" | "video" | "spatial" | "physical" | "functional" | "document" | "photography" | "fashion" | "other" | "unknown";
    role: "primary" | "supporting";
    requirement: "required" | "optional" | "unclear";
    delivery: "design_files" | "finished_media" | "physical_object" | "runnable" | "unspecified";
    evidence: { url: string; quote: string };
};
export type CompetitionCreationSupport = { status: "supported" | "partial" | "unsupported" | "unclear"; reason: string };

export type CompetitionReport = {
    id: string;
    competitionId?: string;
    competitionTitle?: string;
    displayTitle?: string;
    directionId?: string;
    submissionDirectionId?: string;
    creationCategory?: string;
    creationScope?: string;
    directionThemeTask?: string;
    creativeCategories?: { id: string; title: string; description: string; submissionFormat?: string; finalSubmissionFormat?: string; evidence?: { url: string; quote: string }; workItems?: CompetitionWorkItem[]; creationSupport?: CompetitionCreationSupport }[];
    workItems?: CompetitionWorkItem[];
    creationSupport?: CompetitionCreationSupport;
    directions?: CompetitionReport[];
    matchedDirectionIds?: string[];
    directionPending?: boolean;
    independence?: "confirmed" | "unclear";
    sourceHeading?: string;
    sourceHeadings?: string[];
    bindingEvidence?: { url: string; quote: string } | null;
    sourceVersion?: string;
    coverageStatus?: "checked_headings" | "needs_review";
    evidence?: { url: string; quote: string }[];
    missingInformation?: string[];
    eligibilityStatus?: "eligible" | "ineligible" | "unclear";
    title: string;
    track: string;
    designTypes?: DesignDirection[];
    eligibility: string;
    themeTask: string;
    deadline?: string | null;
    submissionFormat: string;
    finalSubmissionFormat?: string;
    fee: string;
    feeStatus?: "free" | "paid" | "unknown";
    aiRule: string;
    aiAllowed?: boolean;
    graphicStatus?: "graphic" | "non_graphic" | "unclear";
    recognized?: boolean;
    registrationUrl: string;
    sourceUrl: string;
    sourceUrls: string[];
    collectedAt: string;
    pendingReason?: string;
    priority?: "a_class" | "recognized";
};

export type CompetitionFeed = {
    version: number;
    source: string;
    sourceUrl: string;
    fetchedAt: string | null;
    items: CompetitionReport[];
    pending: CompetitionReport[];
    recognizedNames: string[];
    aClassSourceUrl?: string;
    importResult?: { nameCount: number; matchedCount: number };
    updating?: boolean;
    updateError?: string;
    checking?: boolean;
    queuedCount?: number;
    failedCount?: number;
    reprocessing?: boolean;
    directionErrors?: Record<string, string>;
    checkError?: string;
    lastUpdate?: { id: string; processed: number; failed: number; completedAt?: string };
    discovery?: {
        checkedOn?: string | null;
        checkedAt?: string | null;
        checkError?: string;
        lastBatch?: { processed: number; failed: number };
    };
};

export type CompetitionIntent = {
    intent: "filter" | "upload_recognition" | "refresh" | "help" | "clarify";
    keywords: string[];
    designTypes: DesignDirection[];
    deadlineDays: number | null;
    priority: "a_class" | "recognized" | "all";
    freeOnly: boolean;
    aiOnly: boolean;
    nextPage?: boolean;
    choices?: string[];
    reply: string;
};

export type CompetitionConversationContext = {
    filter?: CompetitionIntent;
    lastQuestion?: string;
    clarification?: string;
};

