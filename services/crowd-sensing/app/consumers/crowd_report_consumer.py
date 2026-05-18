import json
import logging
from typing import Optional
from kafka import KafkaConsumer
from sqlalchemy.orm import Session
from app.config import settings
from app.database.connection import SessionLocal
from app.database.models import CrowdReport
from app.schemas.crowd import CrowdReportRequest
from app.utils.occupancy import score_to_label
from app.utils.trust_engine import adjust_trust_scores
from app.utils.validation import validate_route_stop

logger = logging.getLogger(__name__)

class CrowdReportConsumer:
    def __init__(self):
        self.topic = settings.kafka_reports_topic
        self.consumer: Optional[KafkaConsumer] = None
        self.running = False

    def start(self):
        try:
            self.consumer = KafkaConsumer(
                self.topic,
                bootstrap_servers=settings.kafka_broker_url,
                group_id=settings.kafka_consumer_group,
                value_deserializer=lambda x: json.loads(x.decode("utf-8")),
                auto_offset_reset="latest",
                enable_auto_commit=True,
            )
            self.running = True
            logger.info(f"Started consuming from topic {self.topic}")
        except Exception as e:
            logger.error(f"Failed to start Kafka consumer: {e}")

    def consume_forever(self, stop_event):
        self.start()
        if not self.consumer:
            return

        while not stop_event.is_set():
            messages = self.consumer.poll(timeout_ms=1000)
            for topic_partition, records in messages.items():
                with SessionLocal() as db:
                    for record in records:
                        try:
                            self._process_message(db, record.value)
                        except Exception as e:
                            logger.error(f"Error processing message: {e}")

        self.consumer.close()
        logger.info("Kafka consumer stopped.")

    def _process_message(self, db: Session, payload: dict):
        # Validate using Pydantic
        report = CrowdReportRequest(**payload)
        
        # Validate against route-service to maintain route-stop geographical integrity in background worker
        try:
            validate_route_stop(report.route_id, report.stop_id)
        except Exception as e:
            detail = getattr(e, "detail", str(e))
            logger.warning(f"Skipping invalid report for route {report.route_id}, stop {report.stop_id}: {detail}")
            return
        
        # Determine label
        label = score_to_label(report.occupancy_score)
        
        # Persist
        db_report = CrowdReport(
            trip_id=report.trip_id,
            route_id=report.route_id,
            direction_id=report.direction_id,
            stop_id=report.stop_id,
            stop_sequence=report.stop_sequence,
            occupancy_score=report.occupancy_score,
            occupancy_label=label,
            passenger_id=report.passenger_id,
            timestamp=report.timestamp,
        )
        db.add(db_report)
        db.commit()
        logger.debug(f"Saved crowd report for trip {report.trip_id} at stop {report.stop_id}")
        
        # Evaluate consensus and adjust trust score
        if report.passenger_id:
            try:
                adjust_trust_scores(db, report.route_id, report.stop_id, report.occupancy_score, report.passenger_id)
            except Exception as e:
                logger.error(f"Failed to adjust trust score for passenger {report.passenger_id}: {e}")
