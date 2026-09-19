# No-training and provider retention (MM-046)

Training on user content is off by default. The visible defaults are:

- `policy/models/consent.yaml`: `no_training_default: true`
- `cross_user_prompt_cache: false`
- provider retention: minimum

`PrivacyService.training_policy()` reports those defaults. Opt-in requires
`Action.MANAGE_ACL` and an explicit `grant_training_opt_in` call. Cross-user
prompt cache must remain false; `assert_no_cross_user_cache` fails closed if
the constant is ever flipped.

Erasure records (`prv_*`) make the subject unreadable. After `retain_until`,
reads fail with `RetentionError`. Exports require `Action.EXPORT` and must
not include `token` or `password` fields.

Residency extension points are `us`, `eu`, and `private_route`. Customer keys
and private routes are preserved on the security control plane; they are not
implied by a remote provider being configured.
