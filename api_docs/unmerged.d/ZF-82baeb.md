* Added the `hover_space` event type and the `hover_spaces` initial-state
  field for authorized Hover Space setup, membership, Source attachment, and
  launch projections.
  Source attachments now include a `can_browse_records` flag and may have the
  `detached` state when their previously confirmed history remains available.
  The projection also includes realm-scoped published Module catalog metadata
  and pinned Space Module installations, including structured Source bindings,
  triggers, activation, and provenance state.
* Added `POST /hover/spaces/{space_id}/generated-items/{generated_item_id}/evidence`
  to resolve exact, authorized evidence for generated Hover items.
