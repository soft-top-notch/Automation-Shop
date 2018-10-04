import os, pika, configparser, json, os.path, csv


# Read config
if "RABBIT_HOST" not in os.environ:
    os.environ["RABBIT_HOST"] = "localhost"

# Find config in different locations
config_file = None
if os.path.isfile('config.ini'):
    config_file = 'config.ini'
elif os.path.isfile('../config.ini'):
    config_file = '../config.ini'
elif os.path.isfile('../tracing/config.ini'):
    config_file = '../tracing/config.ini'
else:
    raise Exception('config.ini not found')

config = configparser.SafeConfigParser(os.environ)
config.read(config_file)

# Check that urls_file is defined and exists
urls_file = config.get('scheduler', 'urls_file')
print(urls_file)

if not urls_file:
    raise Exception('Set "urls_file" in config.ini')

if not os.path.isfile(urls_file):
    raise Exception("Can't open file '{}'".format(urls_file))


# Create RabbitMQ connection
rabbitmq_host = config.get('rabbitmq', 'host', fallback='localhost', raw=False)
rabbitmq_queue = config.get('rabbitmq', 'queue', fallback='trace_tasks')
        
params = pika.ConnectionParameters(host=rabbitmq_host,
    heartbeat_interval=0, connection_attempts=3, retry_delay=1)

connection = pika.BlockingConnection(params)
channel = connection.channel()
channel.queue_declare(queue = rabbitmq_queue, durable=True)

# Read urls and publish messages
with open(urls_file) as f:
    csvreader = csv.reader(f, delimiter=',')
    for row in csvreader:
        url = row[0]
        message = json.dumps({"url": url})

        channel.basic_publish(exchange='',
            routing_key='trace_tasks',
            body=message,
            properties=pika.BasicProperties(
              delivery_mode = 2
           )
        )
    

