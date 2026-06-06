import { useCallback, useEffect, useRef, useState } from "react";
import { getApiClient } from "@/api/client";
import { getSttMode, prefersApiTranscription } from "@/config/stt";

type SpeechRecognitionCtor = new () => SpeechRecognition;

function getRecognitionCtor(): SpeechRecognitionCtor | null {
  const w = window as Window & {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

function canRecordAudio(): boolean {
  return (
    typeof navigator.mediaDevices?.getUserMedia === "function" &&
    typeof window.MediaRecorder !== "undefined"
  );
}

export function useVoiceInput(onFinal: (text: string) => void) {
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [interim, setInterim] = useState("");
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    setSupported(canRecordAudio() || getRecognitionCtor() !== null);
  }, []);

  const cleanupStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    recorderRef.current = null;
    chunksRef.current = [];
  }, []);

  const stopBrowserRecognition = useCallback(() => {
    recognitionRef.current?.stop();
    recognitionRef.current = null;
  }, []);

  const stop = useCallback(() => {
    stopBrowserRecognition();
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
      return;
    }
    setListening(false);
    setInterim("");
    cleanupStream();
  }, [cleanupStream, stopBrowserRecognition]);

  const transcribeBlob = useCallback(
    async (blob: Blob) => {
      setTranscribing(true);
      setInterim("Transcribing…");
      try {
        const { text } = await getApiClient().transcribe(blob);
        if (text.trim()) onFinal(text.trim());
      } catch {
        setInterim("Transcription failed");
      } finally {
        setTranscribing(false);
        setListening(false);
        setInterim("");
        cleanupStream();
      }
    },
    [cleanupStream, onFinal],
  );

  const startBrowserRecognition = useCallback(() => {
    const Ctor = getRecognitionCtor();
    if (!Ctor) return false;

    const recognition = new Ctor();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-GB";

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let draft = "";
      let finalText = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const part = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalText += part;
        else draft += part;
      }
      setInterim(draft);
      if (finalText.trim()) {
        onFinal(finalText.trim());
        stop();
      }
    };

    recognition.onerror = () => stop();
    recognition.onend = () => {
      if (!transcribing) setListening(false);
    };

    recognitionRef.current = recognition;
    recognition.start();
    return true;
  }, [onFinal, stop, transcribing]);

  const startApiRecording = useCallback(async () => {
    if (!canRecordAudio()) return false;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        void transcribeBlob(blob);
      };
      recorderRef.current = recorder;
      recorder.start();
      setListening(true);
      setInterim("Listening…");
      return true;
    } catch {
      cleanupStream();
      return false;
    }
  }, [cleanupStream, transcribeBlob]);

  const start = useCallback(async () => {
    const mode = getSttMode();
    if (mode === "api" || (mode === "auto" && prefersApiTranscription())) {
      const ok = await startApiRecording();
      if (ok) return;
    }
    setListening(true);
    setInterim("Listening…");
    if (!startBrowserRecognition()) {
      setListening(false);
      setInterim("");
    }
  }, [startApiRecording, startBrowserRecognition]);

  const toggle = useCallback(() => {
    if (listening || transcribing) stop();
    else void start();
  }, [listening, start, stop, transcribing]);

  useEffect(() => () => {
    stopBrowserRecognition();
    cleanupStream();
  }, [cleanupStream, stopBrowserRecognition]);

  return { supported, listening, transcribing, interim, toggle, stop };
}
