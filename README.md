[![Ansible Galaxy](https://img.shields.io/ansible/role/46686)](https://galaxy.ansible.com/wcm_io_devops/jenkins_mqtt_publisher)
[![Build Status](https://travis-ci.org/wcm-io-devops/ansible-jenkins-mqtt-publisher.svg?branch=master)](https://travis-ci.org/wcm-io-devops/ansible-jenkins-mqtt-publisher)

# Jenkins MQTT Publisher (jmqttp)

This role deploys a Python-based systemd service that polls a Jenkins
instance for active jobs and publishes [MQTT](https://en.wikipedia.org/wiki/MQTT) messages containing the
build result. It was made to be used together with the wcm.io DevOps
Jenkins Extreme Feedback Device Client
[wcm_io_devops.jenkins_xfd](https://github.com/wcm-io-devops/ansible-jenkins-xfd).

## How does it work?

A Python script constantly polls a configured Jenkins instance's currently building jobs. Each job poll will be started 
in its own thread, so one service can watch multiple jobs at once. The service must be started with a configuration YAML
file in which you have to set the options for your Jenkins server and the MQTT broker to be used.
When a build job has finished, an MQTT message with a configured topic will be sent, which can then be picked up 
by a client that deals with the MQTT payload to control a Cleware device.

**Important** - You have to configure a view on your Jenkins instance that only shows the currently building jobs.
You have to use the [View Job Filters plugin](https://plugins.jenkins.io/view-job-filters/) for this. In the view's
configuration, you have to click:

    "Add Job Filter" > "Build Statuses Filter" > tick "Currently Building" > "Match Type": "Exclude Unmatched"

## Script

The script is located at `/opt/jmqttp`. You can start it manually for debugging purposes by running
    
    /usr/bin/python3 /opt/jmqttp/jmqttp.py --config /opt/jmqttp/config.yml --log debug
    
Make sure to stop the `jmqttp` service before!

## Role variables

    jmqttp_pip_packages: []  # See defaults/main.yml
    
The required pip packages to install.

    jmqttp_os_packages: []  # See defaults/main.yml
    
The required OS packages to install.

    jmqttp_owner: jmqttp
    jmqttp_group: "{{ jmqttp_owner }}"
    
Owner and group for files and folders, as well as the systemd service.

    jmqttp_basedir: /opt/jmqttp
    
Base directory for the script.

    jmqttp_script: "{{ jmqttp_basedir }}/jmqttp.py"
    
Path to the script.

    jmqttp_config: "{{ jmqttp_basedir }}/config.yml"
    
Path to the script's configuration file.

    jmqttp_mqtt_broker: localhost

URL of the MQTT broker to which messages shall be published.

    jmqttp_mqtt_port: 1883

The port of the host on which the MQTT broker listens.

    #jmqttp_mqtt_topic: jenkins/foo

The topic under which MQTT messages shall be published.

    #jmqttp_jenkins_url: http://localhost:8280

The URL of the Jenkins host to be polled.

    #jmqttp_jenkins_user: admin

The username for the Jenkins instance.

    #jmqttp_jenkins_password: admin

The password for the Jenkins instance.

    #jmqttp_jenkins_view: currently_building

The view on the Jenkins instance to be watched.

    jmqttp_jenkins_poll_frequency: 10

The frequency in seconds by which the Jenkins instance will be polled.

## Example

This will deploy a systemd service that polls a Jenkins instance running on your local machine and publishes MQTT
messages under the topic `foo/bar`.

    - name: Setup jmqttp's
      hosts: jmqttp
      vars:
        jmqttp_mqtt_topic: foo/bar
        jmqttp_jenkins_url: http://localhost:8080
        jmqttp_jenkins_user: admin
        jmqttp_jenkins_password: admin
        jmqttp_jenkins_view: currently_building
      roles:
        - role: wcm_io_devops.jenkins_mqtt_publisher
          tags:
            - jmqttp

**Note:** For a more serious usecase, you should encrypt your credentials with Ansible Vault.
