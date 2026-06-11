import { Button, Input } from "@nextui-org/react";
import { useEffect, useState } from "react";
import { useApi } from "@/providers/ApiProvider";
import { useSession } from "@/providers/SessionProvider";
import { motion, AnimatePresence } from "framer-motion";

const TUBE_OPTIONS = [
  { id: "central", label: "Central", color: "border-red-500 bg-red-50 text-red-800 hover:bg-red-100" },
  { id: "jubilee", label: "Jubilee", color: "border-slate-400 bg-slate-50 text-slate-800 hover:bg-slate-100" },
  { id: "elizabeth-line", label: "Elizabeth", color: "border-purple-500 bg-purple-50 text-purple-800 hover:bg-purple-100" },
  { id: "northern", label: "Northern", color: "border-zinc-800 bg-zinc-50 text-zinc-900 hover:bg-zinc-200" },
  { id: "district", label: "District", color: "border-emerald-600 bg-emerald-50 text-emerald-800 hover:bg-emerald-100" },
  { id: "victoria", label: "Victoria", color: "border-cyan-500 bg-cyan-50 text-cyan-800 hover:bg-cyan-100" },
  { id: "piccadilly", label: "Piccadilly", color: "border-blue-700 bg-blue-50 text-blue-800 hover:bg-blue-100" },
  { id: "bakerloo", label: "Bakerloo", color: "border-amber-700 bg-amber-50 text-amber-900 hover:bg-amber-100" },
];

const TRAVEL_STYLES = [
  { id: "tube", label: "Tube & Rail Devotee", desc: "You rely on Tunnels and lines daily", icon: "🚇" },
  { id: "ev", label: "EV/Autonomous Driver", desc: "You track chargers & road congestions", icon: "⚡" },
  { id: "bike", label: "Active Cyclist / Scooter", desc: "Scenic routes, docks, and clean air paths", icon: "🚲" },
  { id: "bus", label: "Bus & Street Explorer", desc: "Avoid the underground; ride the streets", icon: "🚌" },
];

const COMMUTE_PRESETS_MORNING = [
  { label: "🌅 Early Bird (06:00 - 08:00)", value: "06:00-08:00" },
  { label: "💼 Standard 9-to-5 (08:00 - 09:30)", value: "08:00-09:30" },
  { label: "☕ Late Start (09:30 - 11:00)", value: "09:30-11:00" },
  { label: "🏡 No Commute / Remote", value: "none" },
];

const COMMUTE_PRESETS_EVENING = [
  { label: "🌆 Early Exit (16:00 - 17:30)", value: "16:00-17:30" },
  { label: "🏃 Rush Hour (17:00 - 19:30)", value: "17:00-19:30" },
  { label: "🌙 Late Return (19:30 - 21:00)", value: "19:30-21:00" },
  { label: "🏡 No commute back", value: "none" },
];

type OnboardingDialogProps = {
  open: boolean;
  onComplete: () => void;
};

export function OnboardingDialog({ open, onComplete }: OnboardingDialogProps) {
  const client = useApi();
  const { sessionId } = useSession();
  const [step, setStep] = useState(0);
  const [lines, setLines] = useState<string[]>(["central", "jubilee"]);
  const [areas, setAreas] = useState("E15, EC2A");
  const [travelStyle, setTravelStyle] = useState("tube");
  const [ev, setEv] = useState(false);
  const [morning, setMorning] = useState("08:00-09:30");
  const [evening, setEvening] = useState("17:00-19:30");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open || !sessionId) return;
    client
      .getPreferences()
      .then((prefs) => {
        if (prefs.onboarding_complete) {
          onComplete();
        } else {
          if (prefs.tube_lines.length) setLines(prefs.tube_lines);
          if (prefs.areas.length) setAreas(prefs.areas.join(", "));
          setEv(prefs.ev_enabled);
          if (prefs.ev_enabled) setTravelStyle("ev");
          setMorning(prefs.commute_morning || "08:00-09:30");
          setEvening(prefs.commute_evening || "17:00-19:30");
        }
      })
      .catch(() => {});
  }, [client, onComplete, open, sessionId]);

  if (!open) return null;

  const toggleLine = (line: string) => {
    setLines((prev) =>
      prev.includes(line) ? prev.filter((l) => l !== line) : [...prev, line],
    );
  };

  const handleTravelStyleSelect = (styleId: string) => {
    setTravelStyle(styleId);
    if (styleId === "ev") {
      setEv(true);
    } else {
      setEv(false);
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      await client.putPreferences({
        tube_lines: travelStyle === "tube" ? lines : [],
        areas: areas
          .split(",")
          .map((a) => a.trim().toUpperCase())
          .filter(Boolean),
        ev_enabled: ev,
        commute_morning: morning,
        commute_evening: evening,
        onboarding_complete: true,
      });
      onComplete();
    } finally {
      setSaving(false);
    }
  };

  const nextStep = () => setStep((s) => s + 1);
  const prevStep = () => setStep((s) => Math.max(0, s - 1));

  const pageVariants = {
    initial: { opacity: 0, x: 20 },
    enter: { opacity: 1, x: 0, transition: { duration: 0.25, ease: "easeOut" as const } },
    exit: { opacity: 0, x: -20, transition: { duration: 0.25, ease: "easeIn" as const } },
  };


  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-md">
      <div className="relative w-full max-w-lg rounded-3xl border border-white/20 bg-white/85 p-6 shadow-2xl backdrop-blur-xl ring-1 ring-black/5 overflow-hidden">
        {/* Subtle background glow decorative lines */}
        <div className="absolute -left-10 -top-10 h-32 w-32 rounded-full bg-cyan-400/20 blur-2xl pointer-events-none" />
        <div className="absolute -right-10 -bottom-10 h-32 w-32 rounded-full bg-emerald-400/20 blur-2xl pointer-events-none" />

        <div className="relative z-10">
          <div className="flex justify-between items-center mb-4">
            <span className="text-[10px] font-bold uppercase tracking-widest bg-gradient-to-r from-cyan-600 to-emerald-600 bg-clip-text text-transparent">
              DISRUPTRON ONBOARDING
            </span>
            <span className="text-xs text-slate-500 font-medium">
              Step {step + 1} of 5
            </span>
          </div>

          {/* Simple progress bar */}
          <div className="h-1.5 w-full bg-slate-100 rounded-full mb-6 overflow-hidden">
            <motion.div
              className="h-full bg-gradient-to-r from-cyan-500 to-emerald-400"
              initial={{ width: "20%" }}
              animate={{ width: `${((step + 1) / 5) * 100}%` }}
              transition={{ duration: 0.3 }}
            />
          </div>

          <AnimatePresence mode="wait">
            {step === 0 && (
              <motion.div
                key="step0"
                variants={pageVariants}
                initial="initial"
                animate="enter"
                exit="exit"
                className="space-y-4"
              >
                <h2 className="text-2xl font-bold text-slate-850 tracking-tight leading-snug">
                  Let's shape your London mobility footprint 🌍
                </h2>
                <p className="text-slate-600 text-sm leading-relaxed">
                  We run local-first, privacy-safe diagnostics on your daily commutes. No tracking, no data leakage. Let's customise your agent companion.
                </p>
                <div className="pt-2">
                  <Button
                    className="w-full bg-gradient-to-r from-cyan-500 to-emerald-500 text-white font-medium py-6 rounded-2xl shadow-lg shadow-cyan-500/20"
                    onPress={nextStep}
                  >
                    Start Alignment
                  </Button>
                </div>
              </motion.div>
            )}

            {step === 1 && (
              <motion.div
                key="step1"
                variants={pageVariants}
                initial="initial"
                animate="enter"
                exit="exit"
                className="space-y-4"
              >
                <div>
                  <h3 className="text-xl font-bold text-slate-800">
                    How do you navigate London?
                  </h3>
                  <p className="text-slate-500 text-xs mt-1">
                    Select your primary mode of transit. We'll prioritize these feeds.
                  </p>
                </div>

                <div className="grid grid-cols-1 gap-2.5 pt-1">
                  {TRAVEL_STYLES.map((style) => (
                    <button
                      key={style.id}
                      type="button"
                      onClick={() => handleTravelStyleSelect(style.id)}
                      className={`flex items-center gap-4 text-left p-3.5 rounded-2xl border-2 transition-all ${
                        travelStyle === style.id
                          ? "border-cyan-500 bg-cyan-50/50 shadow-md shadow-cyan-100"
                          : "border-slate-100 bg-slate-50/50 hover:bg-slate-100/50 hover:border-slate-200"
                      }`}
                    >
                      <span className="text-2xl">{style.icon}</span>
                      <div>
                        <p className="text-sm font-semibold text-slate-800">{style.label}</p>
                        <p className="text-xs text-slate-500">{style.desc}</p>
                      </div>
                    </button>
                  ))}
                </div>

                <div className="flex gap-3 pt-3">
                  <Button size="md" variant="flat" className="flex-1 rounded-xl" onPress={prevStep}>
                    Back
                  </Button>
                  <Button
                    size="md"
                    className="flex-1 bg-gradient-to-r from-cyan-500 to-emerald-500 text-white font-medium rounded-xl"
                    onPress={nextStep}
                  >
                    Next
                  </Button>
                </div>
              </motion.div>
            )}

            {step === 2 && (
              <motion.div
                key="step2"
                variants={pageVariants}
                initial="initial"
                animate="enter"
                exit="exit"
                className="space-y-4"
              >
                <div>
                  <h3 className="text-xl font-bold text-slate-800">
                    Where is your daily orbit?
                  </h3>
                  <p className="text-slate-500 text-xs mt-1">
                    Enter the postcode sectors you care about (e.g. EC2A, E15, WC1). Keeps exact coordinates fully private.
                  </p>
                </div>

                <div className="space-y-4 py-2">
                  <Input
                    label="Postcode Hubs"
                    value={areas}
                    onValueChange={setAreas}
                    placeholder="e.g. E15, EC2A, SE1"
                    size="md"
                    className="max-w-full"
                    classNames={{
                      inputWrapper: "border-2 border-slate-100 bg-white/70 backdrop-blur-md rounded-xl hover:border-slate-200",
                    }}
                  />
                  {travelStyle === "ev" && (
                    <div className="bg-cyan-50/40 border border-cyan-100 rounded-xl p-3 flex items-start gap-2.5">
                      <span className="text-lg">⚡</span>
                      <div>
                        <p className="text-xs font-semibold text-cyan-800">EV Alerts Activated</p>
                        <p className="text-[11px] text-cyan-700 leading-normal mt-0.5">
                          Disruptron will monitor availability ratios for fast chargers near these postcode sectors.
                        </p>
                      </div>
                    </div>
                  )}
                </div>

                <div className="flex gap-3 pt-3">
                  <Button size="md" variant="flat" className="flex-1 rounded-xl" onPress={prevStep}>
                    Back
                  </Button>
                  <Button
                    size="md"
                    className="flex-1 bg-gradient-to-r from-cyan-500 to-emerald-500 text-white font-medium rounded-xl"
                    onPress={nextStep}
                  >
                    Next
                  </Button>
                </div>
              </motion.div>
            )}

            {step === 3 && (
              <motion.div
                key="step3"
                variants={pageVariants}
                initial="initial"
                animate="enter"
                exit="exit"
                className="space-y-4"
              >
                <div>
                  <h3 className="text-xl font-bold text-slate-800">
                    {travelStyle === "tube"
                      ? "Which Tube lines do you count on?"
                      : "Optional: Commute Tube lines"}
                  </h3>
                  <p className="text-slate-500 text-xs mt-1">
                    We will push alerts for severe delays on these specific routes.
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-2 py-2">
                  {TUBE_OPTIONS.map((line) => {
                    const isSelected = lines.includes(line.id);
                    return (
                      <button
                        key={line.id}
                        type="button"
                        onClick={() => toggleLine(line.id)}
                        className={`flex items-center justify-between p-2.5 rounded-xl border text-left text-xs font-semibold transition-all ${
                          isSelected
                            ? `${line.color} border-current shadow-sm scale-[1.02]`
                            : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
                        }`}
                      >
                        <span>{line.label}</span>
                        {isSelected && <span className="text-sm">✓</span>}
                      </button>
                    );
                  })}
                </div>

                <div className="flex gap-3 pt-3">
                  <Button size="md" variant="flat" className="flex-1 rounded-xl" onPress={prevStep}>
                    Back
                  </Button>
                  <Button
                    size="md"
                    className="flex-1 bg-gradient-to-r from-cyan-500 to-emerald-500 text-white font-medium rounded-xl"
                    onPress={nextStep}
                  >
                    Next
                  </Button>
                </div>
              </motion.div>
            )}

            {step === 4 && (
              <motion.div
                key="step4"
                variants={pageVariants}
                initial="initial"
                animate="enter"
                exit="exit"
                className="space-y-4"
              >
                <div>
                  <h3 className="text-xl font-bold text-slate-800">
                    When are you typically on the move?
                  </h3>
                  <p className="text-slate-500 text-xs mt-1">
                    Disruptron checks feeds proactively right before your active travel hours.
                  </p>
                </div>

                <div className="space-y-3 py-1">
                  <div>
                    <span className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-1.5">
                      Morning Commute
                    </span>
                    <div className="grid grid-cols-2 gap-1.5">
                      {COMMUTE_PRESETS_MORNING.map((preset) => (
                        <button
                          key={preset.value}
                          type="button"
                          onClick={() => setMorning(preset.value)}
                          className={`text-left p-2 rounded-lg text-xs border transition-all ${
                            morning === preset.value
                              ? "border-cyan-500 bg-cyan-50 text-cyan-800 font-semibold"
                              : "border-slate-100 hover:bg-slate-50 text-slate-600"
                          }`}
                        >
                          {preset.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <span className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-1.5">
                      Evening Return
                    </span>
                    <div className="grid grid-cols-2 gap-1.5">
                      {COMMUTE_PRESETS_EVENING.map((preset) => (
                        <button
                          key={preset.value}
                          type="button"
                          onClick={() => setEvening(preset.value)}
                          className={`text-left p-2 rounded-lg text-xs border transition-all ${
                            evening === preset.value
                              ? "border-cyan-500 bg-cyan-50 text-cyan-800 font-semibold"
                              : "border-slate-100 hover:bg-slate-50 text-slate-600"
                          }`}
                        >
                          {preset.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="flex gap-3 pt-3">
                  <Button size="md" variant="flat" className="flex-1 rounded-xl" onPress={prevStep}>
                    Back
                  </Button>
                  <Button
                    size="md"
                    className="flex-1 bg-gradient-to-r from-cyan-500 to-emerald-500 text-white font-medium rounded-xl"
                    isLoading={saving}
                    onPress={() => void save()}
                  >
                    Finish Set Up
                  </Button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
