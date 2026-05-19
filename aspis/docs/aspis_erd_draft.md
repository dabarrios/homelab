# Aspis ERD Draft

Rough first data model. This is not final.

```text
Table Stack {
  id "bigint" [primary key]
  name "varchar"
  path "varchar"
  compose_file "varchar"
  created_at "datetime"
  updated_at "datetime"
}

Table Service {
  id "bigint" [primary key]
  stack_id "bigint"
  name "varchar"
  container_name "varchar"
  image "varchar"
  restart_policy "varchar"
  network_mode "varchar"
  raw_config_json "json"
  created_at "datetime"
  updated_at "datetime"
}

Table ScanRun {
  id "bigint" [primary key]
  target_path "varchar"
  status "varchar"
  started_at "datetime"
  finished_at "datetime"
  summary_json "json"
}

Table Rule {
  id "bigint" [primary key]
  rule_id "varchar"
  name "varchar"
  severity "varchar"
  description "text"
  enabled "boolean"
  metadata_json "json"
}

Table Finding {
  id "bigint" [primary key]
  scan_run_id "bigint"
  stack_id "bigint"
  service_id "bigint"
  rule_id "varchar"
  severity "varchar"
  title "varchar"
  description "text"
  evidence_json "json"
  remediation "text"
  status "varchar"
  created_at "datetime"
}

Table AcceptedRisk {
  id "bigint" [primary key]
  finding_id "bigint"
  reason "text"
  accepted_by "varchar"
  expires_at "datetime"
  created_at "datetime"
}

Table Report {
  id "bigint" [primary key]
  scan_run_id "bigint"
  format "varchar"
  path "varchar"
  created_at "datetime"
}

Table Setting {
  id "bigint" [primary key]
  key "varchar"
  value_json "json"
  updated_at "datetime"
}

Ref: Service.stack_id > Stack.id
Ref: Finding.scan_run_id > ScanRun.id
Ref: Finding.stack_id > Stack.id
Ref: Finding.service_id > Service.id
Ref: Finding.rule_id > Rule.rule_id
Ref: AcceptedRisk.finding_id > Finding.id
Ref: Report.scan_run_id > ScanRun.id
```

## Notes

Maybe accepted risks should attach to:

- exact finding id, or
- rule plus service, so the risk can survive a new scan.

Maybe need separate tables later:

- ports.
- volumes.
- networks.
- environment variables.

For MVP, JSON columns are probably enough.

