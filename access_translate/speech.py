"""SAPI speech output.

Deliberate design choice from the project plan: speaks directly
through Windows SAPI rather than routing through NVDA, JAWS, or
Narrator. This is what makes the tool genuinely universal - SAPI
speech plays through Windows audio regardless of which screen reader,
if any, is running, and sidesteps the fact that Narrator has no public
addon/extension API at all.
"""
import pythoncom
import win32com.client


class Speaker:
    def __init__(self, voice_id="", rate=0, volume=100):
        # Ensure COM is initialized for this thread. wx may have already
        # initialized it as MTA; CoInitializeEx with COINIT_MULTITHREADED
        # is safe to call again on the same thread if it's already MTA,
        # and fixes the silent SAPI no-output bug when wx owns the thread.
        try:
            pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
        except Exception:
            pass  # Already initialized, that's fine
        self.sapi = win32com.client.Dispatch("SAPI.SpVoice")
        self.set_voice(voice_id)
        self.set_rate(rate)
        self.set_volume(volume)
        # SVSFlagsAsync (1) | SVSFPurgeBeforeSpeak (2): interrupt
        # whatever's currently being said rather than queueing.
        self._flags = 1 | 2

    @staticmethod
    def list_voices():
        """Returns [(id, display_name), ...] for every installed SAPI
        voice - ETI-Eloquence, Acapela, any Microsoft voices, etc."""
        sapi = win32com.client.Dispatch("SAPI.SpVoice")
        voices = []
        try:
            for token in sapi.GetVoices():
                voices.append((token.Id, token.GetDescription()))
        except Exception as e:
            print(f"Could not enumerate SAPI voices: {e}")
        return voices

    def set_voice(self, voice_id):
        if not voice_id:
            return
        try:
            for token in self.sapi.GetVoices():
                if token.Id == voice_id:
                    self.sapi.Voice = token
                    return
        except Exception as e:
            print(f"Could not set voice '{voice_id}': {e}")

    def set_rate(self, rate):
        try:
            self.sapi.Rate = int(rate)
        except Exception:
            pass

    def set_volume(self, volume):
        try:
            self.sapi.Volume = int(volume)
        except Exception:
            pass

    def speak(self, text):
        if not text:
            return
        try:
            self.sapi.Speak(text, self._flags)
        except Exception as e:
            print(f"SAPI speech error: {e}")

    def stop(self):
        """Immediately silences whatever this voice is currently
        saying, without queuing anything new. Speaking an empty
        string with SVSFPurgeBeforeSpeak (2) flushes SAPI's queue and
        cuts off playback right away - important for long
        translations, where the reader wants to paste the result into
        a text file and read it with their screen reader instead of
        waiting for SAPI to finish the whole passage."""
        try:
            self.sapi.Speak("", 2)
        except Exception as e:
            print(f"SAPI stop error: {e}")
