#!/bin/bash

IMAGES=("postgres")

function build_image() {
    IMAGE_NAME=$(echo $1 | cut -d "-" -f 1)

    echo "Building ${IMAGE_NAME}..."

    echo "Building development image..."
    docker build -t magicdocu/$IMAGE_NAME -f ./docker/$IMAGE_NAME/Dockerfile .

    if [[ $? != 0 ]]; then
        echo "Failed to build image ${IMAGE_NAME}! Aborting..."
        exit 1
    fi
}

function loop_build() {
    for image in $@; do
        build_image $image
    done
}

if [[ ! -d "./docker" ]]; then
    echo "Running from wrong directory!"
    echo "You should run this from the root directory of the project"
    exit 1
fi

echo "Building images..."
loop_build ${IMAGES[*]}

echo "Everything done!"
exit 0