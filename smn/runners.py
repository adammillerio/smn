#!/usr/bin/env python3
import time
from io import DEFAULT_BUFFER_SIZE
from typing import BinaryIO

from fabric2.runners import Remote as FabricRemote
from invoke.runners import Local as InvokeLocal
from invoke.terminals import character_buffered


class Local(InvokeLocal):
    """Summoner local runner.

    Subclass of the invoke Local runner with some additional customizations.
    """

    # Raise the in_stream read chunk size from 1000 to the default (8192)
    read_chunk_size: int = DEFAULT_BUFFER_SIZE

    def _write_proc_stdin(self, data: bytes) -> None:
        # https://github.com/pyinvoke/invoke/issues/917
        # Replace LF \n with CRLF \r\n in stdin if enabled (see smn.Context.run)
        if self.context.smn_use_crlf and data == b"\n":
            data = b"\r\n"

        # pyre-fixme[16]: `Local` has no attribute `_write_proc_stdin`.
        return super()._write_proc_stdin(data)

    # Method copied verbatim from base runner, with a single modification to only
    # sleep if no data was retrieved from stdin. This speeds up reading from stdin
    # significantly, while avoiding the CPU penalty of disabling sleep entirely.
    # https://github.com/pyinvoke/invoke/blob/506bf4e020c177a03cf4257a22969bad0845e4ee/invoke/runners.py#L834
    # # https://github.com/pyinvoke/invoke/issues/774
    def handle_stdin(
        self,
        input_: BinaryIO,
        output: BinaryIO,
        echo: bool = False,
    ) -> None:
        """
        Read local stdin, copying into process' stdin as necessary.

        Intended for use as a thread target.

        .. note::
            Because real terminal stdin streams have no well-defined "end", if
            such a stream is detected (based on existence of a callable
            ``.fileno()``) this method will wait until `program_finished` is
            set, before terminating.

            When the stream doesn't appear to be from a terminal, the same
            semantics as `handle_stdout` are used - the stream is simply
            ``read()`` from until it returns an empty value.

        :param input_: Stream (file-like object) from which to read.
        :param output: Stream (file-like object) to which echoing may occur.
        :param bool echo: User override option for stdin-stdout echoing.

        :returns: ``None``.

        .. versionadded:: 1.0
        """
        # TODO: reinstate lock/whatever thread logic from fab v1 which prevents
        # reading from stdin while other parts of the code are prompting for
        # runtime passwords? (search for 'input_enabled')
        # TODO: fabric#1339 is strongly related to this, if it's not literally
        # exposing some regression in Fabric 1.x itself.
        closed_stdin = False
        with character_buffered(input_):
            while True:
                data = self.read_our_stdin(input_)
                if data:
                    # Mirror what we just read to process' stdin.
                    # We encode to ensure bytes, but skip the decode step since
                    # there's presumably no need (nobody's interacting with
                    # this data programmatically).
                    self.write_proc_stdin(data)
                    # Also echo it back to local stdout (or whatever
                    # out_stream is set to) when necessary.
                    if echo is None:
                        echo = self.should_echo_stdin(input_, output)
                    if echo:
                        self.write_our_output(stream=output, string=data)
                # Empty string/char/byte != None. Can't just use 'else' here.
                elif data is not None:
                    # When reading from file-like objects that aren't "real"
                    # terminal streams, an empty byte signals EOF.
                    if not self.using_pty and not closed_stdin:
                        self.close_proc_stdin()
                        closed_stdin = True
                # Dual all-done signals: program being executed is done
                # running, *and* we don't seem to be reading anything out of
                # stdin. (NOTE: If we only test the former, we may encounter
                # race conditions re: unread stdin.)
                if self.program_finished.is_set() and not data:
                    break
                if not data:
                    # Take a nap so we're not chewing CPU.
                    time.sleep(self.input_sleep)


class Remote(FabricRemote):
    """Summoner remote runner.

    Subclass of the fabric Remote runner with some additional customizations.
    """

    # Raise the in_stream read chunk size from 1000 to the default (8192)
    read_chunk_size: int = DEFAULT_BUFFER_SIZE

    def _write_proc_stdin(self, data: bytes) -> None:
        # https://github.com/pyinvoke/invoke/issues/917
        # Replace LF \n with CRLF \r\n in stdin if enabled (see smn.Context.run)
        if self.context.smn_use_crlf and data == b"\n":
            data = b"\r\n"

        return super()._write_proc_stdin(data)

    # Method copied verbatim from base runner, with a single modification to only
    # sleep if no data was retrieved from stdin. This speeds up reading from stdin
    # significantly, while avoiding the CPU penalty of disabling sleep entirely.
    # https://github.com/pyinvoke/invoke/blob/506bf4e020c177a03cf4257a22969bad0845e4ee/invoke/runners.py#L834
    # # https://github.com/pyinvoke/invoke/issues/774
    def handle_stdin(
        self,
        input_: BinaryIO,
        output: BinaryIO,
        echo: bool = False,
    ) -> None:
        """
        Read local stdin, copying into process' stdin as necessary.

        Intended for use as a thread target.

        .. note::
            Because real terminal stdin streams have no well-defined "end", if
            such a stream is detected (based on existence of a callable
            ``.fileno()``) this method will wait until `program_finished` is
            set, before terminating.

            When the stream doesn't appear to be from a terminal, the same
            semantics as `handle_stdout` are used - the stream is simply
            ``read()`` from until it returns an empty value.

        :param input_: Stream (file-like object) from which to read.
        :param output: Stream (file-like object) to which echoing may occur.
        :param bool echo: User override option for stdin-stdout echoing.

        :returns: ``None``.

        .. versionadded:: 1.0
        """
        # TODO: reinstate lock/whatever thread logic from fab v1 which prevents
        # reading from stdin while other parts of the code are prompting for
        # runtime passwords? (search for 'input_enabled')
        # TODO: fabric#1339 is strongly related to this, if it's not literally
        # exposing some regression in Fabric 1.x itself.
        closed_stdin = False
        with character_buffered(input_):
            while True:
                data = self.read_our_stdin(input_)
                if data:
                    # Mirror what we just read to process' stdin.
                    # We encode to ensure bytes, but skip the decode step since
                    # there's presumably no need (nobody's interacting with
                    # this data programmatically).
                    self.write_proc_stdin(data)
                    # Also echo it back to local stdout (or whatever
                    # out_stream is set to) when necessary.
                    if echo is None:
                        echo = self.should_echo_stdin(input_, output)
                    if echo:
                        self.write_our_output(stream=output, string=data)
                # Empty string/char/byte != None. Can't just use 'else' here.
                elif data is not None:
                    # When reading from file-like objects that aren't "real"
                    # terminal streams, an empty byte signals EOF.
                    if not self.using_pty and not closed_stdin:
                        self.close_proc_stdin()
                        closed_stdin = True
                # Dual all-done signals: program being executed is done
                # running, *and* we don't seem to be reading anything out of
                # stdin. (NOTE: If we only test the former, we may encounter
                # race conditions re: unread stdin.)
                if self.program_finished.is_set() and not data:
                    break
                if not data:
                    # Take a nap so we're not chewing CPU.
                    time.sleep(self.input_sleep)
