/*
 * CSI4900 bounded UART raw-capture helper.
 *
 * Device mode (QNX): read-only /dev/ser2, monotonic timeout and byte limit.
 * Fixture mode: deterministic binary copy for cross-platform test purposes.
 * Never opens the UART device for output or modifies GPIO/boot configuration.
 * Captures raw evidence only. Use uart_collector_v1 --fixture to decode it.
 */
#ifndef _WIN32
#define _POSIX_C_SOURCE 200809L
#endif
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>
#ifndef _WIN32
#include <sys/select.h>
#include <termios.h>
#include <time.h>
#else
#include <io.h>
#ifndef O_BINARY
#define O_BINARY 0
#endif
#endif

#define MAX_CAPTURE_BYTES (16UL*1024UL*1024UL)
#define MAX_SECONDS 600UL
#define CHUNK 2048U

static void usage(const char *name)
{
    fprintf(stderr, "Usage: %s --raw-output FILE [--fixture INPUT | --device /dev/ser2]\n"
        "        [--seconds 20] [--max-bytes 1048576]\n", name);
}
static int positive(const char *arg, unsigned long limit, unsigned long *out)
{
    char *end = NULL;
    unsigned long number;
    if (!arg || !*arg || *arg == '-') return -1;
    errno = 0;
    number = strtoul(arg, &end, 10);
    if (errno || end == arg || *end != '\0' || number == 0UL || number > limit)
        return -1;
    *out = number;
    return 0;
}
#ifndef _WIN32
static uint64_t milliseconds_now(void)
{
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) != 0)
        return UINT64_MAX;
    return (uint64_t)t.tv_sec * 1000U + (uint64_t)t.tv_nsec / 1000000U;
}
static int set_raw_serial(int fd, struct termios *old_settings)
{
    struct termios settings;
    if (tcgetattr(fd, old_settings) != 0) return -1;
    settings = *old_settings;
    settings.c_iflag &= ~(IGNBRK | BRKINT | PARMRK | ISTRIP | INLCR | IGNCR | ICRNL | IXON);
    settings.c_oflag &= ~OPOST;
    settings.c_lflag &= ~(ECHO | ECHONL | ICANON | ISIG | IEXTEN);
    settings.c_cflag |= CLOCAL | CREAD;
    settings.c_cflag &= ~(CSIZE | PARENB | CSTOPB);
    settings.c_cflag |= CS8;
    settings.c_cc[VMIN] = 0;
    settings.c_cc[VTIME] = 0;
    if (cfsetispeed(&settings, B115200) != 0 ||
        cfsetospeed(&settings, B115200) != 0 ||
        tcsetattr(fd, TCSANOW, &settings) != 0) return -1;
    return 0;
}
#endif
static int write_all(int fd, const uint8_t *bytes, size_t length)
{
    size_t count = 0U;
    while (count < length)
    {
        ssize_t n = write(fd, bytes + count, length - count);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return -1;
        count += (size_t)n;
    }
    return 0;
}
int main(int argc, char **argv)
{
    const char *fixture = NULL, *device = "/dev/ser2", *raw_path = NULL;
    int fixture_seen = 0, device_seen = 0;
    unsigned long seconds = 20UL, limit = 1048576UL;
    for (int i = 1; i < argc; ++i)
    {
        if (!strcmp(argv[i], "--fixture") && i + 1 < argc)
            { fixture = argv[++i]; fixture_seen = 1; }
        else if (!strcmp(argv[i], "--device") && i + 1 < argc)
            { device = argv[++i]; device_seen = 1; }
        else if (!strcmp(argv[i], "--raw-output") && i + 1 < argc)
            raw_path = argv[++i];
        else if (!strcmp(argv[i], "--seconds") && i + 1 < argc)
            { if (positive(argv[++i], MAX_SECONDS, &seconds) != 0)
                { usage(argv[0]); return 2; } }
        else if (!strcmp(argv[i], "--max-bytes") && i + 1 < argc)
            { if (positive(argv[++i], MAX_CAPTURE_BYTES, &limit) != 0)
                { usage(argv[0]); return 2; } }
        else { usage(argv[0]); return 2; }
    }
    if (!raw_path || !*raw_path || (fixture_seen && device_seen))
        { usage(argv[0]); return 2; }
    if (fixture && !strcmp(raw_path, fixture))
        { fprintf(stderr, "Input and output files must differ\n"); return 2; }
#ifdef _WIN32
    if (!fixture_seen)
        { fprintf(stderr, "Live serial is QNX-only in this helper\n"); return 2; }
#endif
    int src = -1, out = -1, read_failed = 0, capture_expired = 0;
    int reached_limit = 0;
    uint64_t total = 0U, elapsed_ms = 0U;
#ifndef _WIN32
    int configured = 0;
    struct termios previous_tty;
    uint64_t started = 0U;
#endif
    src = open(fixture ? fixture : device, O_RDONLY
#ifndef _WIN32
        | (fixture ? 0 : (O_NOCTTY | O_NONBLOCK))
#else
        | O_BINARY
#endif
    );
    if (src < 0) { perror("source"); return 1; }
#ifndef _WIN32
    if (!fixture)
    {
        if (set_raw_serial(src, &previous_tty) != 0)
            { perror("serial configure"); close(src); return 1; }
        configured = 1;
        started = milliseconds_now();
        if (started == UINT64_MAX)
            { fprintf(stderr, "monotonic clock unavailable\n"); tcsetattr(src,TCSANOW,&previous_tty);close(src);return 1; }
    }
#endif
    out = open(raw_path, O_WRONLY | O_CREAT | O_EXCL
#ifdef _WIN32
        | O_BINARY
#endif
        , 0600);
    if (out < 0)
    {
        perror("raw output; never overwrite existing capture");
#ifndef _WIN32
        if (configured) (void)tcsetattr(src, TCSANOW, &previous_tty);
#endif
        close(src);
        return 1;
    }
    uint8_t buffer[CHUNK];
    for (;;)
    {
#ifndef _WIN32
        if (!fixture)
        {
            uint64_t now = milliseconds_now();
            if (now == UINT64_MAX || now < started)
                { read_failed = 1; break; }
            elapsed_ms = now - started;
            if (elapsed_ms >= (uint64_t)seconds * 1000U)
                { capture_expired = 1; break; }
            uint64_t remaining = (uint64_t)seconds * 1000U - elapsed_ms;
            struct timeval wait;
            wait.tv_sec = (long)((remaining > 250U ? 250U : remaining) / 1000U);
            wait.tv_usec = (long)(((remaining > 250U ? 250U : remaining) % 1000U) * 1000U);
            fd_set selected;
            FD_ZERO(&selected);
            FD_SET(src, &selected);
            int ready = select(src+1, &selected, NULL, NULL, &wait);
            if (ready == 0) continue;
            if (ready < 0)
            {
                if (errno == EINTR) continue;
                perror("serial select"); read_failed = 1; break;
            }
        }
#endif
        if (total >= (uint64_t)limit)
            { reached_limit = 1; break; }
        size_t available = (uint64_t)(limit - total) < sizeof(buffer)
            ? (size_t)(limit-total) : sizeof(buffer);
        ssize_t n = read(src, buffer, available);
        if (n < 0 && errno == EINTR) continue;
#ifndef _WIN32
        if (n < 0 && !fixture && (errno == EAGAIN || errno == EWOULDBLOCK))
            continue;
#endif
        if (n < 0)
            { perror("source read"); read_failed = 1; break; }
        if (n == 0)
        {
            if (fixture) break;
            /* A serial driver may report no available data without EOF. */
            continue;
        }
        if (write_all(out, buffer, (size_t)n) != 0)
            { perror("raw write"); read_failed = 1; break; }
        total += (uint64_t)n;
    }
    if (close(out) != 0) read_failed = 1;
#ifndef _WIN32
    if (configured && tcsetattr(src,TCSANOW,&previous_tty) != 0)
        read_failed = 1;
#endif
    if (close(src) != 0) read_failed = 1;
    fprintf(stderr,
        "raw_bytes=%" PRIu64 " duration_ms=%" PRIu64
        " timed_out=%d limit_reached=%d read_error=%d source=%s\n",
        total,elapsed_ms,capture_expired,reached_limit,read_failed,
        fixture ? "fixture" : "serial");
    if (read_failed) return 1;
    if (total == 0U) return 3; /* valid no-data capture, not a PASS */
    return 0;
}
