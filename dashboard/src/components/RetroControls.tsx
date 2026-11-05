import { Button, Input, Card, type CardProps, type ButtonProps, type InputProps } from "pixel-retroui";

export function RetroButton({ className = "", ...props }: ButtonProps) {
  return (
    <Button
      bg="var(--panel)"
      textColor="var(--ink)"
      borderColor="#65758e"
      shadow="var(--line)"
      {...props}
      className={`retro-control ${className}`}
    />
  );
}

export function RetroInput({ className = "", ...props }: InputProps) {
  return (
    <Input
      bg="var(--panel)"
      textColor="var(--ink)"
      borderColor="#65758e"
      {...props}
      className={`retro-input ${className}`}
    />
  );
}

export function RetroCard({ className = "", ...props }: CardProps) {
  return (
    <Card
      bg="var(--panel)"
      textColor="var(--ink)"
      borderColor="#65758e"
      shadowColor="#080c12"
      {...props}
      className={`retro-surface ${className}`}
    />
  );
}
