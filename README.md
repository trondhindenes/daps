# DAPS
## What is this
dapr.io is awesome, but has some weak spots around lifecycle management. Daps attempts to fix some of these.

## What DAPS does
### Startup robustness
By default, dapr will assume the app container is ready for business as soon as it responds to a tcp ping on its configured port.
This means that dapr disregards regular health check mechanisms, which may cause the app container to start receiving requests before it's ready.

DAPS fixes this by "halting" the tcp ping from dapr until the app container is fully ready.
Configure the readiness path by setting the `daps.io/ready-path` annotation on the pod template. 
Be sure to include the leading slash, for example: `"daps.io/ready-path": "/health"`


### Shutdown coordination
By default, dapr will wait 5 seconds and then exit in response to SIGTERM. 
It does not wait for in-flight pubsub messages to complete (at least not if using RabbitMQ). 
This means that dapr is a rather bad fit for situations where message processing takes a long time, 
especially combined with automatic scaling such as KEDA. Frequent pod replacements increase the chance of lost messages.

DAPS fixes this by adding a prestop hook to both the app container and the dapr sidecar, 
and this hook is used to coordinate shutdown of containers. The Dapr sidecar is not allowed to exit befure the app container has completed its work.


There are two ways to determine if the app is ready for shutdown (no messages in flight):
- since all messages from Dapr to the app container pass thru DAPS, it can track the number of requests in flight. This is the default behavior.
- It's also possible to implement a "busy" endpoint in the app, which DAPS will call to determine "ready-for-shutdown".
This can be used if the app needs to perform additional (time-consuming) work after sending the "message processing response" back to dapr.
These two modes can be controlled using the `"daps.io/busy-path"` annotation. If this annotation, DAPS will use the specified path to determine business, 
and if the annotation is omitted it will use its internal logic.

It's important to set the pod's `terminationGracePeriodSeconds` so that the application is given sufficient time to complete it's work.

#### Implementing the busy endpoint
Use the annotation `"daps.io/busy-path"` to point to any path.
The endpoint should respond to `GET` requests with a json response like this: `{"busy": true}` or `{"busy": false}`. 
DAPS will keep waiting for the busy flag to become `false`, at which time it will complete the prestop hook which allows containers to shut down. 


### How it works
DAPS uses a mutating webhook to inject a secondary sidecar. This means that dapr-enabled applications will have two sidecar containers: dapr itself and DAPS. 
DAPS rewrites the pod template so that all requests from Dapr to the app is sent thru the DAPS sidecar.


## Limitations
While Dapr supports both http and grpc, DAPS only supports http for now.

## Setup
### Generate certificates for the mutating webhook
```
# https://github.com/surajssd/self-signed-cert#install
self-signed-cert --namespace daps-system --service-name daps-webhook

# copy generated keys from temp dir into this repo's "keys" dir
kubectl --namespace=daps-system create secret tls webhook-certs --cert=keys/server.crt --key=keys/server.key

# this is the ca bundle for the webhook, add to res/mutate.yaml
openssl base64 -A < "keys/ca.crt"
```

## Rebuild containers
```
docker build -t trondhindenes/daps-webhook .
docker build -f Dockerfile_sidecar -t trondhindenes/daps-sidecar .

docker push trondhindenes/daps-webhook
docker push trondhindenes/daps-sidecar
```