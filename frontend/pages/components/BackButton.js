import Link from "next/link";
import { ArrowLeft } from 'lucide-react';

export default function BackButton({ href, label, className = "" }) {
  const classes = `px-6 py-3 border border-border text-secondary rounded-xl hover:text-primary hover:border-accent-cyan/30 transition-colors flex items-center gap-2 ${className}`;
  return (
    <Link href={href} className={classes}>
      <ArrowLeft className="h-4 w-4" />
      {label}
    </Link>
    
  );
}


