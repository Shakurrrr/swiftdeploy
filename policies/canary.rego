package swiftdeploy.canary

import future.keywords.if
import future.keywords.in

default allow := false

allow if {
    count(violations) == 0
}

violations contains msg if {
    input.error_rate_percent > data.thresholds.max_error_rate_percent
    msg := sprintf(
        "Error rate %.2f%% exceeds maximum %.2f%%",
        [input.error_rate_percent, data.thresholds.max_error_rate_percent]
    )
}

violations contains msg if {
    input.p99_latency_ms > data.thresholds.max_p99_latency_ms
    msg := sprintf(
        "P99 latency %.0fms exceeds maximum %.0fms",
        [input.p99_latency_ms, data.thresholds.max_p99_latency_ms]
    )
}

decision := {
    "allow":      allow,
    "violations": violations,
    "domain":     "canary",
    "checked_at": input.timestamp,
    "input_summary": {
        "error_rate_percent": input.error_rate_percent,
        "p99_latency_ms":     input.p99_latency_ms,
    },
}
