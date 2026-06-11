import { Image as ImageIcon } from "@deemlol/next-icons";
import { Send } from "@deemlol/next-icons";
import { Button, Input } from "@nextui-org/react";
import { useRef, useState } from "react";

type TextInputBarProps = {
  disabled?: boolean;
  onSend: (text: string, image?: File) => void;
};

export function TextInputBar({ disabled, onSend }: TextInputBarProps) {
  const [text, setText] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const submit = () => {
    if (!text.trim() && !image) return;
    onSend(text.trim() || "What's in this image?", image ?? undefined);
    setText("");
    setImage(null);
    if (fileRef.current) fileRef.current.value = "";
  };

  return (
    <div className="flex gap-2 shrink-0 flex-1 min-w-0">
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => setImage(e.target.files?.[0] ?? null)}
      />
      <Button
        isIconOnly
        variant="flat"
        className="shrink-0 min-w-11"
        isDisabled={disabled}
        onPress={() => fileRef.current?.click()}
        aria-label="Upload image"
      >
        <ImageIcon size={20} strokeWidth={1.75} />
      </Button>
      <Input
        value={text}
        onValueChange={setText}
        placeholder={image ? "Add a question about the image…" : "Ask about London transport…"}
        isDisabled={disabled}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            submit();
          }
        }}
        classNames={{
          inputWrapper: "border border-white/10 bg-[#0d1117]/60 hover:border-cyan-neon/40 focus-within:border-cyan-neon/60 shadow-sm text-text font-sans",
          input: "text-text placeholder:text-muted",
        }}
      />
      <Button
        isIconOnly
        className="bg-cyan-neon text-obsidian hover:bg-cyan-neon/90 hover:scale-[1.02] active:scale-[0.98] transition-all duration-200 shrink-0 min-w-11 shadow-[0_0_15px_rgba(102,252,241,0.3)] font-mono"
        isDisabled={disabled || (!text.trim() && !image)}
        onPress={submit}
        aria-label="Send message"
      >
        <Send size={20} strokeWidth={2} color="#08090C" />
      </Button>
    </div>
  );
}
