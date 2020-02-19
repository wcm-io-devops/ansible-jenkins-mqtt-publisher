import jenkins
import paho.mqtt.client as mqtt

import argparse
import logging
import random
import re
import sys
import systemd.daemon
from threading import Thread
import time
import yaml


def on_connect(client, userdata, flags, rc):
    """Callback function for the MQTT broker connection.

    :param client: The client instance for this callback.
    :param userdata: The private user data as set in Client() or user_data_set().
    :param flags: Response flags sent by the broker.
    :param rc: The connection result.
    :return: None.
    """

    if rc == 0:
        global mqtt_connected
        mqtt_connected = True
        logging.info("Connected to MQTT broker")
    else:
        logging.critical("Connection to MQTT broker failed")


def job_query(jenkins_job):
    """Polls Jenkins for a specific job and publishes MQTT messages."""

    logging.info(f"Starting poll thread for {jenkins_job}")
    last_build_number = server.get_job_info(jenkins_job)["lastBuild"]["number"]
    build_info = server.get_build_info(jenkins_job, last_build_number)
    is_building = bool(build_info["building"])

    if is_building:
        while True:
            live_build_info = server.get_build_info(jenkins_job, last_build_number)
            if live_build_info["building"]:
                logging.debug(f"Job {jenkins_job} is still building")
                time.sleep(config["jenkins"]["poll_frequency"] * DELAY_MULTIPLIER)
            else:
                logging.info(f"Job {jenkins_job} has finished, publishing MQTT message")

                client.publish(config["mqtt"]["topic"], construct_payload(
                    build_number=live_build_info["number"],
                    build_result=live_build_info["result"],
                    build_result_color=jenkins_color[live_build_info["result"]],
                    build_url=live_build_info["url"],
                    jenkins_url=config["jenkins"]["url"],
                    job_base_name=re.sub(r"^.*/(.*)$", r"\1", jenkins_job),
                    job_name=jenkins_job,
                    timestamp=int(time.time())
                )
                               )

                logging.debug(f"Removing {jenkins_job} from polling list")
                global poll_threads
                poll_threads.remove(jenkins_job)

                break


def construct_payload(build_number, build_result, build_result_color, build_url, jenkins_url, job_base_name,
                      job_name, timestamp):
    """Composes the payload for an MQTT message."""

    return f"""
        BUILD_NUMBER: '{build_number}'
        BUILD_RESULT: '{build_result}'
        BUILD_RESULT_COLOR: '{build_result_color}'
        BUILD_URL: '{build_url}'
        JENKINS_URL: '{jenkins_url}'
        JOB_BASE_NAME: '{job_base_name}'
        JOB_NAME: '{job_name}'
        TIMESTAMP: {timestamp}
    """


jenkins_color = {
    "SUCCESS": "green",
    "UNSTABLE": "yellow",
    "FAILURE": "red"
}

if __name__ == "__main__":

    DELAY_MULTIPLIER = random.uniform(1, 1.5)

    # Create a list that holds names of jobs that are currently being polled in a dedicated thread.
    poll_threads = []

    # Read config file path from command line arguments.
    parser = argparse.ArgumentParser(description="Foobar write some doc...")
    parser.add_argument("--config", dest="config", default="config.yml", type=str,
                        help="Path to the configuration file.")
    parser.add_argument("--log", dest="loglevel", default="info", type=str,
                        help="Loglevel (debug, info, warning, error, critical)")
    args = parser.parse_args()

    config_path = args.config
    loglevel = args.loglevel

    # Set log level.
    numeric_level = getattr(logging, loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError("Invalid log level: %s" % loglevel)
    logging.basicConfig(level=numeric_level)

    # Read configuration from YML file.
    logging.info("Reading config")
    with open(config_path, "r") as stream:
        try:
            config = yaml.safe_load(stream)
        except yaml.YAMLError as e:
            print(e)
            sys.exit(1)

    # Create a Jenkins server object.
    logging.info(f"Connecting to Jenkins at {config['jenkins']['url']}")
    server = jenkins.Jenkins(url=config["jenkins"]["url"],
                             username=config["jenkins"]["username"],
                             password=config["jenkins"]["password"])
    logging.info("Connected to Jenkins")

    # Connect to the MQTT broker
    mqtt_connected = False
    client = mqtt.Client("jenkins-mqtt-poll")
    client.on_connect = on_connect
    logging.info(f"Connecting to MQTT broker at {config['mqtt']['broker']}")
    client.connect(config["mqtt"]["broker"], config["mqtt"]["port"])
    client.loop_start()

    while not mqtt_connected:
        time.sleep(1)

    # Notify systemd that the service is ready.
    systemd.daemon.notify("READY=1")

    try:
        while True:
            # Wait for a random amount of seconds * the given poll frequency until polling.
            time.sleep(config["jenkins"]["poll_frequency"] * DELAY_MULTIPLIER)

            # Get a list of all jobs, so we can match the fullname properties.
            all_jobs = server.get_all_jobs()

            # Get a list of currently building jobs.
            currently_building_jobs = [_["fullname"] for _ in server.get_jobs(view_name=config["jenkins"]["view"])]
            currently_building_jobs_helper = []

            # Replace "short" fullnames with verbose fullnames of currently building jobs.
            for job in currently_building_jobs:
                pattern = re.compile(r".*%s.*" % job)
                currently_building_jobs_helper = [_["fullname"] for _ in all_jobs if pattern.search(_["fullname"])]
            currently_building_jobs = currently_building_jobs_helper
            logging.debug(f"Currently building jobs: {currently_building_jobs}")

            # Start a new thread for each job, but only it it is not already being polled in an existing thread.
            for job in currently_building_jobs:
                if job not in poll_threads:
                    thread = Thread(target=job_query, args=(job,))
                    poll_threads.append(job)
                    thread.start()
                else:
                    logging.debug(f"{job} is already being polled")
                    continue

    except:
        client.disconnect()
        client.loop_stop()
        sys.exit(1)
