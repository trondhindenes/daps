import base64
import copy
import http

import jsonpatch
from flask import Flask, jsonify, request, make_response

app = Flask(__name__)


@app.route("/validate", methods=["POST"])
def validate():
    allowed = True
    try:
        for container_spec in request.json["request"]["object"]["spec"]["containers"]:
            if "env" in container_spec:
                allowed = False
    except KeyError:
        pass
    return jsonify(
        {
            "response": {
                "allowed": allowed,
                "uid": request.json["request"]["uid"],
                "status": {"message": "env keys are prohibited"},
            }
        }
    )


@app.route("/mutate", methods=["POST"])
def mutate():
    spec = request.json["request"]["object"]

    orig_spec = copy.deepcopy(spec)
    has_dapr_sidecar = len([x for x in spec["spec"]["containers"] if x["name"] == "daprd"]) > 0
    has_daps_sidecar = len([x for x in spec["spec"]["containers"] if x["name"] == "daps"]) > 0
    has_dapr_annotation = spec["metadata"]["annotations"].get("dapr.io/enabled") == "true"
    has_daps_annotation = spec["metadata"]["annotations"].get("daps.io/enabled") == "true"
    daps_ready_path = spec["metadata"]["annotations"].get("daps.io/ready-path", "/api/ready")
    daps_busy_path = spec["metadata"]["annotations"].get("daps.io/busy-path", "/api/busy")
    do_mutate = False

    if has_dapr_sidecar and has_dapr_annotation and has_daps_annotation:
        do_mutate = True

    if do_mutate:
        pod_termination_gracetime_secs = spec["spec"]["terminationGracePeriodSeconds"]
        application_port = spec["metadata"]["annotations"].get("dapr.io/app-port")
        dapr_container = [x for x in spec["spec"]["containers"] if x["name"] == "daprd"][0]
        app_container = [x for x in spec["spec"]["containers"] if x["name"] == "app"][0]

        dapr_container["lifecycle"] = {
            "preStop": {
                "httpGet": {
                    "port": 9696,
                    "path": "daps/dapr-shutdown"
                }
            }
        }
        dapr_app_port_index = dapr_container["args"].index('--app-port') + 1
        dapr_container["args"][dapr_app_port_index] = "9696"
        app_container["lifecycle"] = {
            "preStop": {
                "httpGet": {
                    "port": 9696,
                    "path": "daps/app-shutdown"
                }
            }
        }
        if not has_daps_sidecar:
            spec["spec"]["containers"].append(
                {
                    "name": "daps",
                    "image": "trondhindenes/daps-sidecar:latest",
                    "env": [
                        {
                            "name": "POD_TERMINATION_GRACE_PERIOD_SECONDS",
                            "value": str(pod_termination_gracetime_secs)
                        },
                        {
                            "name": "MAIN_APP_PORT",
                            "value": application_port
                        },
                        {
                            "name": "MAIN_APP_READY_PROBE_PATH",
                            "value": daps_ready_path
                        },
                        {
                            "name": "MAIN_APP_BUSY_PROBE_PATH",
                            "value": daps_busy_path
                        }
                    ],
                    "lifecycle": {
                        "preStop": {
                            "httpGet": {
                                "port": 9696,
                                "path": "daps/self-shutdown"
                            }
                        }
                    }
                }
            )

    patch = jsonpatch.JsonPatch.from_diff(orig_spec, spec)
    print(patch)
    response = {
        "apiVersion": "admission.k8s.io/v1",
        "kind": "AdmissionReview",
        "response": {
            "uid": request.json["request"]["uid"],
            "allowed": True,
            "patch": base64.b64encode(str(patch).encode()).decode(),
            "patchType": "JSONPatch",
        }
    }
    resp = make_response(jsonify(response), 200)
    resp.headers["content-Type"] = "application/json-patch+json"
    return resp


@app.route("/health", methods=["GET"])
def health():
    return "", http.HTTPStatus.NO_CONTENT


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)  # pragma: no cover
