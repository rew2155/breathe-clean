import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import paho.mqtt.client as mqtt

from messaging.messages import PurifierCommandMessage
from messaging.transport import (
    MessageDisposition,
    MqttSettings,
    MqttTransportError,
    PahoMqttTransport,
)


class FakeReasonCode:
    def __init__(self, is_failure: bool = False):
        self.is_failure = is_failure

    def __str__(self):
        return "failure" if self.is_failure else "success"


class FakePublishResult:
    def __init__(self, rc=mqtt.MQTT_ERR_SUCCESS, published=True):
        self.rc = rc
        self.published = published
        self.waited = False

    def wait_for_publish(self, timeout):
        self.waited = True

    def is_published(self):
        return self.published


class FakePahoClient:
    def __init__(self):
        self.on_connect = None
        self.on_disconnect = None
        self.callbacks = {}
        self.subscriptions = []
        self.published = []
        self.publish_result = FakePublishResult()
        self.connection_failure = False
        self.loop_started = False
        self.acknowledged = []

    def connect(self, host, port, keepalive):
        self.connection_args = (host, port, keepalive)
        self.on_connect(
            self,
            None,
            None,
            FakeReasonCode(self.connection_failure),
            None,
        )

    def loop_start(self):
        self.loop_started = True

    def loop_stop(self):
        self.loop_started = False

    def disconnect(self):
        return mqtt.MQTT_ERR_SUCCESS

    def publish(self, topic, payload, qos, retain):
        self.published.append((topic, payload, qos, retain))
        return self.publish_result

    def subscribe(self, topic, qos):
        self.subscriptions.append((topic, qos))
        return mqtt.MQTT_ERR_SUCCESS, 1

    def message_callback_add(self, topic, callback):
        self.callbacks[topic] = callback

    def ack(self, message_id, qos):
        self.acknowledged.append((message_id, qos))
        return mqtt.MQTT_ERR_SUCCESS


class PahoMqttTransportTests(unittest.TestCase):
    def setUp(self):
        self.client = FakePahoClient()
        self.transport = PahoMqttTransport(
            MqttSettings(),
            client=self.client,
            operation_timeout=0.01,
        )

    def command(self):
        return PurifierCommandMessage(
            message_id=uuid4(),
            purifier_id=123,
            desired_state=True,
            issued_at=datetime.now(timezone.utc),
        )

    def test_connects_and_renews_existing_subscriptions(self):
        self.transport.subscribe(
            "breathe-clean/v1/sensors/+/readings",
            lambda *_: MessageDisposition.ACKNOWLEDGE,
        )

        self.transport.connect()

        self.assertEqual(
            self.client.connection_args,
            ("localhost", 1883, 60),
        )
        self.assertEqual(
            self.client.subscriptions,
            [("breathe-clean/v1/sensors/+/readings", 1)],
        )
        self.assertTrue(self.client.loop_started)

    def test_publishes_validated_json_with_qos_one(self):
        self.transport.connect()
        command = self.command()

        self.transport.publish("breathe-clean/v1/purifiers/123/commands", command)

        topic, payload, qos, retained = self.client.published[0]
        self.assertEqual(topic, "breathe-clean/v1/purifiers/123/commands")
        self.assertEqual(
            PurifierCommandMessage.model_validate_json(payload),
            command,
        )
        self.assertEqual(qos, 1)
        self.assertFalse(retained)
        self.assertTrue(self.client.publish_result.waited)

    def test_rejects_publish_while_disconnected(self):
        with self.assertRaises(MqttTransportError):
            self.transport.publish("topic", self.command())

    def test_reports_rejected_connection(self):
        self.client.connection_failure = True

        with self.assertRaises(MqttTransportError):
            self.transport.connect()

    def test_dispatches_message_to_wildcard_handler(self):
        received = []
        topic_filter = "breathe-clean/v1/sensors/+/readings"
        self.transport.subscribe(
            topic_filter,
            lambda topic, payload: (
                received.append((topic, payload))
                or MessageDisposition.ACKNOWLEDGE
            ),
        )
        mqtt_message = SimpleNamespace(
            topic="breathe-clean/v1/sensors/123/readings",
            payload=b"payload",
            mid=10,
            qos=1,
        )

        self.client.callbacks[topic_filter](self.client, None, mqtt_message)

        self.assertEqual(
            received,
            [("breathe-clean/v1/sensors/123/readings", b"payload")],
        )
        self.assertEqual(self.client.acknowledged, [(10, 1)])

    def test_does_not_acknowledge_message_marked_for_retry(self):
        topic_filter = "breathe-clean/v1/sensors/+/readings"
        self.transport.subscribe(
            topic_filter,
            lambda *_: MessageDisposition.RETRY,
        )
        mqtt_message = SimpleNamespace(
            topic="breathe-clean/v1/sensors/123/readings",
            payload=b"payload",
            mid=10,
            qos=1,
        )

        self.client.callbacks[topic_filter](self.client, None, mqtt_message)

        self.assertEqual(self.client.acknowledged, [])


if __name__ == "__main__":
    unittest.main()
