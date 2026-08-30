import * as z from "zod/mini";

import * as channel from "./channel.ts";

const legacy_evidence_schema = z.object({
    evidence_ref: z.string(),
    source_ref: z.string(),
    sender: z.object({ref: z.string(), display_name: z.string()}),
    timestamp: z.string(),
    content: z.object({
        text: z.nullable(z.string()),
        voice_transcript: z.nullable(z.string()),
        media_description: z.nullable(z.string()),
    }),
    media: z.nullable(
        z.object({
            type: z.string(),
            mime_type: z.nullable(z.string()),
            byte_size: z.nullable(z.number()),
            sha256: z.nullable(z.string()),
            available: z.boolean(),
        }),
    ),
});

const grouped_message_schema = z.object({
    message_id: z.number(),
    sender_name: z.string(),
    timestamp: z.number(),
    rendered_content: z.string(),
});

const grouped_evidence_schema = z.object({
    groups: z.array(
        z.object({
            topic: z.object({
                stream_id: z.number(),
                topic_name: z.string(),
                kind: z.enum(["regular", "source"]),
                provider_name: z.optional(z.string()),
            }),
            messages: z.array(grouped_message_schema),
        }),
    ),
    forbidden_count: z.number(),
});

const legacy_evidence_response_schema = z.object({evidence: z.array(legacy_evidence_schema)});
const error_response_schema = z.object({retryable: z.optional(z.boolean())});

type LegacyEvidence = z.infer<typeof legacy_evidence_schema>;
type GroupedEvidence = z.infer<typeof grouped_evidence_schema>;

export type PresentedEvidence = {
    groups: {
        topic: GroupedEvidence["groups"][number]["topic"];
        messages: {
            message_id?: number;
            can_open_message: boolean;
            stream_id?: number;
            topic_name?: string;
            sender_name: string;
            timestamp: string;
            display_timestamp: string;
            rendered_content?: string;
            legacy_content?: LegacyEvidence["content"];
            media?: LegacyEvidence["media"];
        }[];
    }[];
    forbidden_count: number;
};

function display_timestamp(value: string | number): string {
    const date = typeof value === "number" ? new Date(value * 1000) : new Date(value);
    return new Intl.DateTimeFormat(undefined, {dateStyle: "medium", timeStyle: "short"}).format(
        date,
    );
}

export function present_evidence(response: unknown): PresentedEvidence {
    const grouped = grouped_evidence_schema.safeParse(response);
    if (grouped.success) {
        return {
            forbidden_count: grouped.data.forbidden_count,
            groups: grouped.data.groups.map((group) => ({
                topic: group.topic,
                messages: group.messages.map((message) => ({
                    ...message,
                    can_open_message: true,
                    stream_id: group.topic.stream_id,
                    topic_name: group.topic.topic_name,
                    timestamp: new Date(message.timestamp * 1000).toISOString(),
                    display_timestamp: display_timestamp(message.timestamp),
                })),
            })),
        };
    }

    const {evidence} = legacy_evidence_response_schema.parse(response);
    return {
        forbidden_count: 0,
        groups:
            evidence.length === 0
                ? []
                : [
                      {
                          topic: {
                              stream_id: 0,
                              topic_name: "Sources",
                              kind: "source" as const,
                          },
                          messages: evidence.map((item) => ({
                              sender_name: item.sender.display_name,
                              can_open_message: false,
                              timestamp: item.timestamp,
                              display_timestamp: display_timestamp(item.timestamp),
                              legacy_content: item.content,
                              media: item.media,
                          })),
                      },
                  ],
    };
}

export type EvidenceError = {retryable: boolean};

export function fetch_evidence(
    url: string,
    callbacks: {
        success: (evidence: PresentedEvidence) => void;
        error: (error: EvidenceError) => void;
    },
): void {
    void channel.post({
        url,
        success(response) {
            let evidence: PresentedEvidence;
            try {
                evidence = present_evidence(response);
            } catch {
                callbacks.error({retryable: false});
                return;
            }
            callbacks.success(evidence);
        },
        error(xhr) {
            const parsed = error_response_schema.safeParse(xhr.responseJSON);
            callbacks.error({
                retryable:
                    parsed.success && parsed.data.retryable !== undefined
                        ? parsed.data.retryable
                        : [429, 502, 503, 504].includes(xhr.status),
            });
        },
    });
}
