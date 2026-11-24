/*
 * STM32 v1 trace-frame collector for offline fixtures or QNX serial devices.
 *
 * Output is timestamp_us,EVENT,id for the existing R2 normalized-event CLI.
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
#include <unistd.h>

#ifndef _WIN32
#include <termios.h>
#endif

#define FRAME_SYNC_0 0xA5U
#define FRAME_SYNC_1 0x5AU
#define PROTOCOL_VERSION 1U
#define HEADER_SIZE 10U
#define EVENT_SIZE 13U
#define MAX_FRAME_SIZE 118U
#define READ_BUFFER_SIZE 1024U

typedef struct
{
  uint32_t serial;
  uint32_t cycles;
  uint32_t previous_cycles;
  uint64_t timestamp_us;
  uint32_t fractional_cycles;
  int previous_cycles_valid;
  int previous_sequence_valid;
  int frame_count;
  int crc_error_count;
  int frame_gap_count;
  int invalid_frame_count;
  uint32_t task_map[256];
  int task_map_count;
} Collector;

static uint16_t read_u16(const uint8_t *p)
{
  return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

static uint32_t read_u32(const uint8_t *p)
{
  return (uint32_t)p[0] |
         ((uint32_t)p[1] << 8) |
         ((uint32_t)p[2] << 16) |
         ((uint32_t)p[3] << 24);
}

static uint16_t crc16(const uint8_t *data, size_t length)
{
  uint16_t crc = 0xFFFFU;
  for (size_t i = 0; i < length; ++i)
  {
    crc ^= (uint16_t)data[i] << 8;
    for (uint8_t bit = 0; bit < 8; ++bit)
    {
      crc = (crc & 0x8000U) ? (uint16_t)((crc << 1) ^ 0x1021U)
                            : (uint16_t)(crc << 1);
    }
  }
  return crc;
}

static uint32_t fnv1a(const char *text)
{
  uint32_t hash = 2166136261U;
  while (*text)
  {
    hash ^= (uint8_t)*text++;
    hash *= 16777619U;
  }
  return hash;
}

static void init_default_task_map(Collector *c)
{
  c->task_map[0] = fnv1a("SensorTask");
  c->task_map[1] = fnv1a("ControlTask");
  c->task_map[2] = fnv1a("LoggerTask");
  c->task_map[3] = fnv1a("CommunicationTask");
  c->task_map_count = 4;
}

static int map_object(Collector *c, uint32_t object_hash)
{
  for (int i = 0; i < c->task_map_count; ++i)
  {
    if (c->task_map[i] == object_hash)
      return i + 1;
  }
  if (c->task_map_count < 256)
  {
    c->task_map[c->task_map_count++] = object_hash;
    return c->task_map_count;
  }
  return -1;
}

static void emit_gap(Collector *c, FILE *out)
{
  /* Invalidate downstream state at the most recent known event time. */
  fprintf(out, "%" PRIu64 ",GAP,-1\n", c->timestamp_us);
}

static uint64_t cycles_to_us(Collector *c, uint32_t cycles, uint32_t cycles_per_us)
{
  if (!c->previous_cycles_valid)
  {
    c->previous_cycles = cycles;
    c->previous_cycles_valid = 1;
    c->timestamp_us = 0;
  }
  else
  {
    uint32_t delta;
    if (cycles >= c->previous_cycles)
      delta = cycles - c->previous_cycles;
    else
      delta = UINT32_MAX - c->previous_cycles + cycles + 1U;
    uint64_t total_cycles = (uint64_t)delta + c->fractional_cycles;
    c->timestamp_us += total_cycles / cycles_per_us;
    c->fractional_cycles = (uint32_t)(total_cycles % cycles_per_us);
    c->previous_cycles = cycles;
  }
  return c->timestamp_us;
}

static int parse_frame(Collector *c, const uint8_t *frame, size_t size,
                       FILE *out, uint32_t cycles_per_us)
{
  if (size < HEADER_SIZE || frame[0] != FRAME_SYNC_0 || frame[1] != FRAME_SYNC_1)
  {
    c->invalid_frame_count++;
    return -1;
  }
  if (frame[2] != PROTOCOL_VERSION)
  {
    c->invalid_frame_count++;
    return -1;
  }

  uint16_t declared_length = read_u16(&frame[3]);
  uint32_t frame_sequence = read_u32(&frame[5]);
  uint8_t event_count = frame[9];
  uint16_t expected_length = (uint16_t)(10U + (uint16_t)event_count * EVENT_SIZE);

  if (declared_length != expected_length ||
      size != (size_t)(2U + declared_length) ||
      event_count > 8U)
  {
    c->invalid_frame_count++;
    emit_gap(c, out);
    return -1;
  }

  size_t crc_offset = 10U + (size_t)event_count * EVENT_SIZE;
  if (crc_offset + 2U != size)
  {
    c->invalid_frame_count++;
    emit_gap(c, out);
    return -1;
  }

  uint16_t received_crc = read_u16(&frame[crc_offset]);
  uint16_t calculated_crc = crc16(&frame[2], crc_offset - 2U);
  if (received_crc != calculated_crc)
  {
    c->crc_error_count++;
    emit_gap(c, out);
    return -1;
  }

  if (c->previous_sequence_valid && frame_sequence != c->serial + 1U)
  {
    c->frame_gap_count++;
    emit_gap(c, out);
  }
  c->serial = frame_sequence;
  c->previous_sequence_valid = 1;
  c->frame_count++;

  for (uint8_t i = 0; i < event_count; ++i)
  {
    const uint8_t *event = &frame[10U + (size_t)i * EVENT_SIZE];
    uint8_t type = event[0];
    uint32_t object_hash = read_u32(&event[1]);
    uint32_t cycles = read_u32(&event[5]);
    uint64_t timestamp_us = cycles_to_us(c, cycles, cycles_per_us);

    if (type != 1U && type != 2U)
    {
      c->invalid_frame_count++;
      emit_gap(c, out);
      return -1;
    }
    if (type == 1U || type == 2U)
    {
      int id = map_object(c, object_hash);
      if (id > 0)
      {
        fprintf(out, "%" PRIu64 ",%s,%d\n",
                timestamp_us, type == 1U ? "SWITCH_IN" : "SWITCH_OUT", id);
      }
      else
      {
        emit_gap(c, out);
      }
    }
  }
  return 0;
}

static int configure_serial(int fd)
{
#ifdef _WIN32
  (void)fd;
  return -1;
#else
  struct termios settings;
  if (tcgetattr(fd, &settings) != 0)
    return -1;
  /* cfmakeraw is not POSIX and may be hidden by strict C11/QNX headers. */
  settings.c_iflag &= ~(IGNBRK | BRKINT | PARMRK | ISTRIP | INLCR | IGNCR | ICRNL | IXON);
  settings.c_oflag &= ~OPOST;
  settings.c_lflag &= ~(ECHO | ECHONL | ICANON | ISIG | IEXTEN);
  cfsetispeed(&settings, B115200);
  cfsetospeed(&settings, B115200);
  settings.c_cflag |= CLOCAL | CREAD;
  settings.c_cflag &= ~CSTOPB;
  settings.c_cflag &= ~PARENB;
  settings.c_cflag &= ~CSIZE;
  settings.c_cflag |= CS8;
  settings.c_cc[VMIN] = 1;
  settings.c_cc[VTIME] = 0;
  if (tcsetattr(fd, TCSANOW, &settings) != 0)
    return -1;
  tcflush(fd, TCIFLUSH);
  return 0;
#endif
}

static int read_source(int fd, uint8_t *buffer, size_t size)
{
  ssize_t n = read(fd, buffer, size);
  if (n < 0)
  {
    if (errno == EINTR)
      return -2; /* Interrupted read: retry without claiming EOF. */
    return -1;
  }
  return (int)n;
}

static void print_usage(const char *program)
{
  fprintf(stderr,
          "Usage: %s [--device /dev/ser2 | --fixture file]\n"
          "          [--output file] [--cycles-per-us 16]\n",
          program);
}

int main(int argc, char **argv)
{
  const char *device = "/dev/ser2";
  const char *fixture = NULL;
  const char *output_path = NULL;
  uint32_t cycles_per_us = 16U;
  Collector c;
  memset(&c, 0, sizeof(c));
  init_default_task_map(&c);

  for (int i = 1; i < argc; ++i)
  {
    if (strcmp(argv[i], "--device") == 0 && i + 1 < argc)
      device = argv[++i];
    else if (strcmp(argv[i], "--fixture") == 0 && i + 1 < argc)
      fixture = argv[++i];
    else if (strcmp(argv[i], "--output") == 0 && i + 1 < argc)
      output_path = argv[++i];
    else if (strcmp(argv[i], "--cycles-per-us") == 0 && i + 1 < argc)
    {
      char *end = NULL;
      errno = 0;
      unsigned long value = strtoul(argv[++i], &end, 10);
      if (errno || !end || *end || value == 0 || value > 1000)
      {
        print_usage(argv[0]);
        return 2;
      }
      cycles_per_us = (uint32_t)value;
    }
    else
    {
      print_usage(argv[0]);
      return 2;
    }
  }

  FILE *out = stdout;
  if (output_path)
  {
    out = fopen(output_path, "w");
    if (!out)
    {
      perror(output_path);
      return 1;
    }
  }

  int fd = -1;
  FILE *fixture_file = NULL;
  if (fixture)
  {
    fixture_file = fopen(fixture, "rb");
    if (!fixture_file)
    {
      perror(fixture);
      if (output_path)
        fclose(out);
      return 1;
    }
  }
  else
  {
#ifdef _WIN32
    fd = open(device, O_RDONLY); /* Never used for live UART on Windows. */
#else
    fd = open(device, O_RDONLY | O_NOCTTY);
#endif
    if (fd < 0)
    {
      perror(device);
      if (output_path)
        fclose(out);
      return 1;
    }
    if (configure_serial(fd) != 0)
    {
      fprintf(stderr, "Failed to configure %s at 115200 8N1\n", device);
      close(fd);
      if (output_path)
        fclose(out);
      return 1;
    }
  }

  uint8_t buffer[4096];
  size_t buffered = 0;
  int io_error = 0;

  for (;;)
  {
    size_t available = sizeof(buffer) - buffered;
    if (available == 0U)
    {
      /* Valid v1 frames are bounded to 116 bytes; saturation is corrupt. */
      c.invalid_frame_count++;
      emit_gap(&c, out);
      buffered = 0;
      available = sizeof(buffer);
    }

    int n = fixture_file
                ? (int)fread(buffer + buffered, 1, available, fixture_file)
                : read_source(fd, buffer + buffered, available);

    if (n == -2)
      continue; /* interrupted serial read */
    if (n < 0)
    {
      fprintf(stderr, "Serial read failed: %s\n", strerror(errno));
      io_error = 1;
      break;
    }
    if (n == 0 && !fixture_file)
    {
      fprintf(stderr, "Serial device returned EOF\n");
      io_error = 1;
      break;
    }

    if (n > 0)
      buffered += (size_t)n;

    /*
     * Drain every complete frame already buffered, including when one read
     * contains several frames or the fixture is at EOF.
     */
    for (;;)
    {
      if (buffered < 2U)
        break;

      size_t start = 0;
      while (start + 1U < buffered &&
             !(buffer[start] == FRAME_SYNC_0 && buffer[start+1] == FRAME_SYNC_1))
        start++;

      if (start > 0U)
      {
        /* Any discarded bytes between valid frames are a loss of evidence. */
        if (c.previous_sequence_valid)
        {
          c.invalid_frame_count++;
          emit_gap(&c, out);
        }
        memmove(buffer, buffer + start, buffered - start);
        buffered -= start;
      }
      if (buffered < HEADER_SIZE)
        break;

      if (buffer[2] != PROTOCOL_VERSION)
      {
        c.invalid_frame_count++;
        emit_gap(&c, out);
        memmove(buffer, buffer + 1U, buffered - 1U);
        buffered--;
        continue;
      }

      uint16_t declared_length = read_u16(&buffer[3]);
      size_t frame_size = 2U + declared_length;
      if (declared_length < 23U || declared_length > 114U)
      {
        c.invalid_frame_count++;
        emit_gap(&c, out);
        memmove(buffer, buffer + 1U, buffered - 1U);
        buffered--;
        continue;
      }
      if (buffered < frame_size)
        break;

      (void)parse_frame(&c, buffer, frame_size, out, cycles_per_us);
      memmove(buffer, buffer + frame_size, buffered - frame_size);
      buffered -= frame_size;
    }

    if (n == 0 && fixture_file)
    {
      if (ferror(fixture_file))
      {
        fprintf(stderr, "Fixture read failed\n");
        io_error = 1;
      }
      if (buffered)
      {
        /* A partial frame is invalid even if the file's last byte was read. */
        c.invalid_frame_count++;
        emit_gap(&c, out);
        fprintf(stderr, "Incomplete trailing fixture bytes: %zu\n",buffered);
      }
      break;
    }
  }

  fprintf(stderr,
          "frames=%d crc_errors=%d frame_gaps=%d invalid_frames=%d\n",
          c.frame_count, c.crc_error_count, c.frame_gap_count,
          c.invalid_frame_count);

  if (fixture_file)
    fclose(fixture_file);
  else
    close(fd);
  if (output_path)
    fclose(out);
  return io_error || c.frame_gap_count || c.invalid_frame_count || c.crc_error_count ? 1 : 0;
}
