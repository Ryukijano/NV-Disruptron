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
          inputWrapper: "border-2 border-slate-200 bg-white shadow-sm",
        }}
      />
      <Button
        isIconOnly
        color="primary"
        className="bg-gradient-to-r from-cyan-500 to-emerald-500 text-white shrink-0 min-w-11"
        isDisabled={disabled || (!text.trim() && !image)}
        onPress={submit}
        aria-label="Send message"
      >
        <Send size={20} strokeWidth={1.75} color="#ffffff" />
      </Button>
    </div>
  );
}
