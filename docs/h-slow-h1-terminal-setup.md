# H1 Demo terminal binding

This is the only Windows-host setup required before the fixed H_SLOW
read-only operations can observe the dedicated Demo account. It does not
enable trading, create an order route, or change the existing M1 terminal.

1. Install or select a **separate** MetaTrader 5 terminal instance for H_SLOW.
   Do not reuse the terminal operated by M1.
2. Sign that terminal into the approved `GOMarketsMU-Demo` H1 account using
   the normal broker/terminal login flow. Do not store its password in this
   repository, terminal binding file, console output, evidence, or a tracked
   configuration file.
3. On the Windows host, copy
   `t480/h_slow_mt5.local.example.json` to:

   ```text
   %USERPROFILE%\Documents\Code\forex-h-slow\mt5.local.json
   ```

4. Replace only `python_path`, `terminal_path`, and `expected_login`. Keep
   `account_label` exactly `H1_demo`. `terminal_path` must name the separate
   terminal's `terminal64.exe`; it must not be the M1 terminal path.
5. Run only the fixed read-only preflight:

   ```text
   python3 scripts/t480_adapter.py execute --operation h_slow_demo_preflight
   ```

   A successful result contains an opaque account-scope digest, never the
   login or a credential. A refusal changes nothing and must be corrected
   before any later H_SLOW activation work.

After a successful preflight, the fixed financing and reconciliation snapshots
can observe the same terminal. All three operations remain read-only. A
separate reviewed activation configuration and fixed execution adapter are
still required before any Demo order could exist.
