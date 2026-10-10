#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# build_payment_aggregators_flow.py
#
# RapidPro/goflow requires every element (node, action, exit, case, category,
# router) to have a valid UUID4. This reads the readable flows/mpesa_source.json,
# assigns deterministic *fresh* UUID4s to every non-UUID identifier (rewriting
# cross-references and the _ui node keys), adds the missing switch-router uuid,
# and wraps the flows in an export bundle with a catch-all trigger scoped to a
# group and the External channel.
#
# Output: flows/payment_aggregators.json  (import with Org.import_app)
# ---------------------------------------------------------------------------
import json
import os
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "flows", "mpesa_source.json")
OUT = os.path.join(HERE, "..", "flows", "payment_aggregators.json")

FLOW_UUID = "5b0d47cc-ff19-4e50-911d-7dcfdbe4c00f"          # keep the (valid) flow uuid
CHANNEL_UUID = "4c335860-00cb-4c05-844d-836d271facf5"       # External (EX) channel
CHANNEL_NAME = "smsgateway"
GROUP_UUID = "99a4a5d2-b2e0-4bb4-a19a-24462af10c01"         # PaymentAggregators
GROUP_NAME = "PaymentAggregators"

UUID_KEYS = ("uuid", "destination_uuid", "exit_uuid", "category_uuid", "default_category_uuid")


def is_uuid(value):
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def collect_ids(obj, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in UUID_KEYS and isinstance(v, str) and v and not is_uuid(v):
                out.add(v)
            collect_ids(v, out)
    elif isinstance(obj, list):
        for item in obj:
            collect_ids(item, out)


def rewrite(obj, mapping):
    if isinstance(obj, dict):
        new = {}
        for k, v in obj.items():
            if k in UUID_KEYS and isinstance(v, str) and v in mapping:
                new[k] = mapping[v]
            else:
                new[k] = rewrite(v, mapping)
        return new
    if isinstance(obj, list):
        return [rewrite(v, mapping) for v in obj]
    return obj


def main():
    with open(SRC) as f:
        bundle = json.load(f)

    flows = bundle["flows"]
    flows[0]["uuid"] = FLOW_UUID

    # 1) fresh UUID4 for every non-UUID identifier across all flows
    ids = set()
    for flow in flows:
        collect_ids(flow, ids)
    mapping = {i: str(uuid.uuid4()) for i in ids}

    processed = []
    for flow in flows:
        flow = rewrite(flow, mapping)

        # 2) the switch routers need their own uuid
        for node in flow["nodes"]:
            if "router" in node and "uuid" not in node["router"]:
                node["router"]["uuid"] = str(uuid.uuid4())

        # 3) remap the _ui node keys so editor positions survive
        if "_ui" in flow and "nodes" in flow["_ui"]:
            flow["_ui"]["nodes"] = {mapping.get(k, k): v for k, v in flow["_ui"]["nodes"].items()}

        processed.append(flow)

    # 4) wrap in a fresh export bundle + catch-all trigger for the group/channel
    export = {
        "version": "13",
        "site": bundle.get("site", "https://app.rapidpro.io"),
        "flows": processed,
        "campaigns": [],
        "triggers": [
            {
                "trigger_type": "C",  # Catch All
                "flow": {"uuid": FLOW_UUID, "name": processed[0]["name"]},
                "channel": {"uuid": CHANNEL_UUID, "name": CHANNEL_NAME},
                "groups": [{"uuid": GROUP_UUID, "name": GROUP_NAME}],
                "exclude_groups": [],
            }
        ],
        "fields": [],
        "groups": [],
    }

    with open(OUT, "w") as f:
        json.dump(export, f, indent=2)
        f.write("\n")

    print(f"wrote {os.path.relpath(OUT, os.path.join(HERE, '..'))} ({len(ids)} ids remapped)")


if __name__ == "__main__":
    main()
