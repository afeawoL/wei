#####################
# WEI Configuration	#
#####################

# Adjust these parameters to meet your needs
# You can override these at run time by running `make <target> <VARIABLE>="..."`

# Project Configuration
PROJECT_DIR := $(abspath $(MAKEFILE_DIR))
WORKCELLS_DIR := $(PROJECT_DIR)/tests/workcells
WORKCELL_FILENAME := test_workcell.yaml

# Python Configuration
PYPROJECT_TOML := $(PROJECT_DIR)/pyproject.toml
PROJECT_VERSION := $(shell sed -n 's/version = "\([^"]*\)"/\1/p' $(PYPROJECT_TOML) | head -n 1)

# Docker Configuration
COMPOSE_FILE := $(PROJECT_DIR)/compose.yaml
DOCKERFILE := $(PROJECT_DIR)/Dockerfile
DOCKERFILE_TEST := $(PROJECT_DIR)/tests/Dockerfile.test
# Make sure this file is in .gitignore or equivalent
ENV_FILE := $(PROJECT_DIR)/.env
REGISTRY := ghcr.io
ORGANIZATION := ad-sdl
IMAGE_NAME := wei
IMAGE := $(REGISTRY)/$(ORGANIZATION)/$(IMAGE_NAME)
IMAGE_TEST := $(IMAGE)_test

# This should match the name of your app's service in the compose file
APP_NAME := test_app
# This should be the command to run your app in the container
APP_COMMAND :=
# This is where the data from the workcell will be stored
# If these directories don't exist, they will be created
WEI_DATA_DIR := $(PROJECT_DIR)/.wei
REDIS_DIR := $(WEI_DATA_DIR)/redis
# Whether or not to send events to Diaspora (set to true to turn on)
USE_DIASPORA := false
# This is the default target to run when you run `make` with no arguments
.DEFAULT_GOAL := help

########################
# Config-related Rules #
########################

# Generate our .env whenever we change our config
NOT_PHONY += .env
.env: $(MAKEFILE_LIST) pyproject.toml
	@echo Generating .env...
	@echo "# THIS FILE IS AUTOGENERATED, CHANGE THE VALUES IN THE MAKEFILE" > $(ENV_FILE)
	@echo "USER_ID=$(shell id -u)" >> $(ENV_FILE)
	@echo "GROUP_ID=$(shell id -g)" >> $(ENV_FILE)
# The following adds every variable in the Makefiles to the .env file,
# except for everything in ENV_FILTER and ENV_FILTER itself
	@$(foreach v,\
		$(filter-out $(ENV_FILTER) ENV_FILTER,$(.VARIABLES)),\
		echo "$(v)=$($(v))" >> $(ENV_FILE);)

init: .env $(WEI_DATA_DIR) $(REDIS_DIR) # Do the initial configuration of the project

$(WEI_DATA_DIR):
	mkdir -p $(WEI_DATA_DIR)

$(REDIS_DIR):
	mkdir -p $(REDIS_DIR)
