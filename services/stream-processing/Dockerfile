FROM flink:1.17.1-scala_2.12

# Install python3 and pip
RUN apt-get update -y && \
    apt-get install -y python3 python3-pip python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Create alias for python
RUN ln -s /usr/bin/python3 /usr/bin/python

# Set working directory
WORKDIR /opt/flink/usrlib

# Copy requirements and install
COPY services/stream-processing/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Download Kafka Connector JAR
RUN wget -P /opt/flink/lib/ https://repo.maven.apache.org/maven2/org/apache/flink/flink-sql-connector-kafka/1.17.1/flink-sql-connector-kafka-1.17.1.jar

# Copy application code
COPY services/stream-processing/app ./app
COPY schemas ./schemas

# The command is usually set in docker-compose for jobmanager/taskmanager
