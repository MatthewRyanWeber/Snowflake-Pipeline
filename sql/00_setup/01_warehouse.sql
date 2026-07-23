-- Phase 0 · Compute. Idempotent: CREATE ... IF NOT EXISTS preserves an existing WH.

USE ROLE SYSADMIN;

-- WHY: XSMALL + 60s auto-suspend + initially-suspended protects the 30-day trial credits.
CREATE WAREHOUSE IF NOT EXISTS &{sf_warehouse}
  WAREHOUSE_SIZE     = '&{sf_wh_size}'
  AUTO_SUSPEND       = &{sf_wh_auto_suspend}
  AUTO_RESUME        = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Pipeline compute — keep XSMALL with aggressive auto-suspend (trial credits)';

-- Re-running ALTER keeps the warehouse aligned with config even if it pre-existed.
ALTER WAREHOUSE &{sf_warehouse} SET
  WAREHOUSE_SIZE = '&{sf_wh_size}'
  AUTO_SUSPEND   = &{sf_wh_auto_suspend}
  AUTO_RESUME    = TRUE;

GRANT USAGE   ON WAREHOUSE &{sf_warehouse} TO ROLE &{sf_role};
GRANT OPERATE ON WAREHOUSE &{sf_warehouse} TO ROLE &{sf_role};
