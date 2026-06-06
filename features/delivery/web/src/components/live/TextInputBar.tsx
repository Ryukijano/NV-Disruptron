import { Send } from "@deemlol/next-icons";
import { Button, Input } from "@nextui-org/react";
import { useState } from "react";

type TextInputBarProps = {
  disabled?: boolean;
  onSend: (text: string) => void;
};

export function TextInputBar({ disabled, onSend }: TextInputBarProps) {
  const [text, setText] = useState("");

  const submit = () => {
    if (!text.trim()) return;
    onSend(text);
    setText("");
  };

  return (
    <div className="flex gap-2 shrink-0">
      <Input
        value={text}
        onValueChange={setText}
        placeholder="Ask about London transport…"
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
        isDisabled={disabled || !text.trim()}
        onPress={submit}
        aria-label="Send message"
      >
        <Send size={20} strokeWidth={1.75} color="#ffffff" />
      </Button>
    </div>
  );
}
