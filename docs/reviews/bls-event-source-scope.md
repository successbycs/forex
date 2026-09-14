# BLS event-source scope

Reviewed 2026-09-12 for the owner-directed Wave 2 ingestion work.

The [BLS copyright statement](https://www.bls.gov/opub/copyright-information.htm)
identifies published material as public domain, except previously copyrighted
photographs and illustrations, and requests attribution. Its emblem is a
registered trademark. Our scope is attributed calendar text and retained HTML
responses, not linked images or emblem reuse. This is a source-specific
engineering usage assessment, not blanket rights for other publishers.

The [September monthly list](https://www.bls.gov/schedule/2026/09_sched_list.htm)
has Date, Time and Release columns and explicitly declares Eastern Time.
Select CPI and Employment Situation by exact release family and reference
month; unrelated releases and holidays are out of scope. No forecast, actual
value, news sentiment or directional rule is introduced.

`config/event_sources.json` is the canonical W2 declaration. It is separate
from the four-candidate historical M7 snapshot, which remains unchanged.
Source usage qualification does not establish complete calendar coverage,
historical publication timing or trading authority. The deployed fixed
collector subsequently retained successful raw September and October 2026
HTML responses through the approved shared-T480 path, with HTTP 200 status
and no parser quarantine. That confirms this narrowly declared collection
path's present availability; it does not authenticate historic publication
times or justify bypassing any future access denial.

This addition does not change M1's inputs, listener, risk configuration or
broker adapter, and does not close or revalidate any formal milestone. Before
remote collection release, bind this declaration and the parser/storage
versions to that component's deployment record. Any subsequent attachment
to operating records must account for the affected contract and proof.
