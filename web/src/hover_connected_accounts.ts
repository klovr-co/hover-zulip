import * as z from "zod/mini";

export const connected_account_selector_schema = z.object({
    selector_type: z.string(),
    source_ref: z.string(),
    display_name: z.string(),
});

export const connected_account_grant_schema = z.object({
    id: z.number(),
    account_id: z.number(),
    user_id: z.number(),
    state: z.enum(["active", "revoked"]),
    all_selectors: z.boolean(),
    selectors: z.array(connected_account_selector_schema),
});

export const connected_account_schema = z.object({
    id: z.number(),
    provider_key: z.string(),
    provider_name: z.string(),
    external_account_id: z.string(),
    display_name: z.string(),
    connection_kind: z.enum(["remote_studio", "native_integration"]),
    incoming_webhook_bot_id: z.nullable(z.number()),
    created_by_id: z.nullable(z.number()),
    owner_id: z.nullable(z.number()),
    approval_state: z.enum(["pending", "approved", "revoked"]),
    health_status: z.enum(["unknown", "healthy", "degraded", "unavailable"]),
    health_checked_at: z.nullable(z.string()),
});

export const connected_accounts_response_schema = z.object({
    connected_accounts: z.array(connected_account_schema),
    connected_account_grants: z.array(connected_account_grant_schema),
});

export type ConnectedAccount = z.output<typeof connected_account_schema>;
export type ConnectedAccountGrant = z.output<typeof connected_account_grant_schema>;

let accounts_by_id = new Map<number, ConnectedAccount>();
let grants_by_id = new Map<number, ConnectedAccountGrant>();

export function initialize(params: {
    hover_connected_accounts: ConnectedAccount[];
    hover_connected_account_grants: ConnectedAccountGrant[];
}): void {
    accounts_by_id = new Map(
        params.hover_connected_accounts.map((account) => [account.id, account]),
    );
    grants_by_id = new Map(params.hover_connected_account_grants.map((grant) => [grant.id, grant]));
}

export function replace_from_response(raw_data: unknown): void {
    const {connected_accounts, connected_account_grants} =
        connected_accounts_response_schema.parse(raw_data);
    initialize({
        hover_connected_accounts: connected_accounts,
        hover_connected_account_grants: connected_account_grants,
    });
}

export function upsert_account(account: ConnectedAccount): void {
    accounts_by_id.set(account.id, account);
}

export function upsert_grant(grant: ConnectedAccountGrant): void {
    grants_by_id.set(grant.id, grant);
}

export function get_account(account_id: number): ConnectedAccount | undefined {
    return accounts_by_id.get(account_id);
}

export function get_accounts(): ConnectedAccount[] {
    return accounts_by_id.values().toArray().toSorted(
        (a, b) =>
            a.provider_name.localeCompare(b.provider_name) ||
            a.display_name.localeCompare(b.display_name),
    );
}

export function get_grants_for_account(account_id: number): ConnectedAccountGrant[] {
    return grants_by_id
        .values()
        .filter((grant) => grant.account_id === account_id)
        .toArray()
        .toSorted((a, b) => a.user_id - b.user_id);
}
