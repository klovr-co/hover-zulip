FROM ubuntu:24.04@sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517

ARG HOST_UID=1000
ARG HOST_GID=1000

ENV DEBIAN_FRONTEND=noninteractive \
    LC_ALL=C.UTF-8 \
    PATH=/workspace/.venv/bin:/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin

RUN ln -sf /usr/share/zoneinfo/Etc/UTC /etc/localtime \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        libasound2t64 \
        passwd \
        python3 \
        sudo \
    && rm -rf /var/lib/apt/lists/* \
    && if ! getent group "${HOST_GID}" >/dev/null; then groupadd --gid "${HOST_GID}" hover; fi \
    && useradd --uid "${HOST_UID}" --gid "${HOST_GID}" --shell /bin/bash --create-home hover \
    && printf 'hover ALL=(ALL) NOPASSWD: ALL\n' >/etc/sudoers.d/50-hover \
    && printf 'Defaults env_keep += "DEBIAN_FRONTEND"\n' >/etc/sudoers.d/hover-env

WORKDIR /workspace
COPY --chown=${HOST_UID}:${HOST_GID} . /workspace

# Git worktrees carry a .git pointer to a path outside the Docker build
# context.  Provisioning only needs to know this is a development checkout.
RUN rm -f .git \
    && mkdir .git \
    && chown ${HOST_UID}:${HOST_GID} /workspace .git

USER hover
RUN ./tools/provision --build-release-tarball-only

EXPOSE 9991
CMD ["./tools/run-dev", "--streamlined", "--no-clear-memcached", "--interface=0.0.0.0", "--skip-provision-check"]
