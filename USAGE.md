# Using Renewly

A short walkthrough of every screen, using the seeded demo account
`cenius@cenius.ai` / `cenius`.

## Sign in

`/login` is a two-column page: what Renewly does on the left, the sign-in card on the right.
The card shows the demo credentials and a **Fill demo credentials** button, a show/hide
toggle on the password field, and a link to create an account. A wrong password re-renders
the page with one generic message ("Email or password is incorrect.") and keeps your email.

`/signup` creates a local account. Email shape, an 8-character minimum and the confirm field
are all checked server-side; failures are shown inline and keep your email address.

## Dashboard (`/dashboard`)

- **This month / This year** — normalised spend, one line per currency in use, next to the
  active-subscription count.
- **Saved by cancelling** — the monthly and yearly cost of everything you cancelled, per
  currency, excluded from the totals above.
- **Upcoming renewals** — active subscriptions whose next charge falls inside their own
  reminder lead time and within 30 days, soonest first. Countdowns read "today", "in 3 days";
  rows whose stored date had already passed say "overdue date rolled forward".
- **Spend by category** — monthly and yearly columns per currency with a total row.

A brand-new account sees zeroed cards, an empty savings card and a prompt to add the first
subscription.

## Subscriptions (`/subscriptions`)

A dense table of every subscription: name and category, price with cycle
(`15.49 USD / month`), next renewal (rolled forward if stale), reminder lead time, status and
per-row actions. Filter with **All / Active / Cancelled**. Cancelled rows are de-emphasised
and show the cancel date, with **Resume** instead of **Cancel**. **Delete** asks for
confirmation first.

## Add a subscription (`/subscriptions/new`)

Defaults are monthly, USD, a 7-day reminder and a renewal date 30 days out. Fill in a name
and a price (adjust anything else you need), then submit. Validation errors appear beside the field and keep every
value you typed. The new row appears in the list immediately and survives a reload.

## Edit a subscription (`/subscriptions/{id}/edit`)

The same form, pre-filled, with a status line showing active/cancelled and the cancel date.
Saving returns you to the list with a one-line confirmation.

## Command palette

Press **⌘K** / **Ctrl-K** (or the "Jump to…" button in the header) to open the fuzzy
jump-to list: pages plus every subscription you track. Arrow keys move, Enter opens, Escape
closes.

## Keyboard and accessibility notes

- Every form field has a real label; errors are tied to inputs with `aria-invalid` and
  `aria-describedby`.
- Focus rings use the accent colour at a 2px outline, never removed.
- The layout is usable from 360px wide: cards stack, tables scroll horizontally inside their
  own container, and tap targets stay at least 44px tall on small screens.
