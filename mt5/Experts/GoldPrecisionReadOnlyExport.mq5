// Gold Precision Pro: read-only MT5 bar exporter.
// Reads the attached broker symbol's CLOSED M15 rates and writes a local CSV
// snapshot in the MT5 Common\Files sandbox. No network and no trading APIs.
#property strict
#property version   "1.00"
#property description "Exports closed XAU M15 rates for local research only; never places orders."

input string InpConfirmedGoldSymbol = ""; // Must exactly match chart symbol, including broker suffix.
input int    InpBarsToExport = 2000;      // Closed M15 bars only.
input int    InpTimerSeconds = 15;
input string InpOutputFile = "GoldPrecision/xauusd-m15.csv";

datetime g_lastClosedBar = 0;

string IsoUtc(datetime value)
{
   string out = TimeToString(value, TIME_DATE|TIME_SECONDS);
   StringReplace(out, ".", "-");
   StringReplace(out, " ", "T");
   return out + "Z";
}

string IsoUtcMillis(long epoch_milliseconds)
{
   datetime seconds = (datetime)(epoch_milliseconds / 1000);
   string base = IsoUtc(seconds);
   StringReplace(base, "Z", "");
   return base + StringFormat(".%03dZ", (int)(epoch_milliseconds % 1000));
}

bool ExportClosedM15()
{
   if(InpConfirmedGoldSymbol == "" || _Symbol != InpConfirmedGoldSymbol)
   {
      Print("GoldPrecision export stopped: set InpConfirmedGoldSymbol to the exact chart symbol.");
      return false;
   }
   if(InpBarsToExport < 100 || InpBarsToExport > 10000 || InpTimerSeconds < 5)
   {
      Print("GoldPrecision export stopped: invalid bars/timer bounds.");
      return false;
   }
   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int copied = CopyRates(InpConfirmedGoldSymbol, PERIOD_M15, 1, InpBarsToExport, rates);
   if(copied < 100)
   {
      PrintFormat("GoldPrecision export waiting for M15 history: copied=%d", copied);
      return false;
   }
   datetime newest = rates[copied - 1].time;
   if(newest == g_lastClosedBar)
      return true;

   MqlTick quote;
   if(!SymbolInfoTick(InpConfirmedGoldSymbol, quote) || quote.time_msc <= 0 ||
      quote.bid <= 0 || quote.ask < quote.bid)
   {
      Print("GoldPrecision export waiting for a valid current Bid/Ask quote.");
      return false;
   }

   int file = FileOpen(InpOutputFile, FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON, ',', CP_UTF8);
   if(file == INVALID_HANDLE)
   {
      PrintFormat("GoldPrecision export file error=%d", GetLastError());
      return false;
   }
   FileWrite(file, "symbol", "timeframe", "bar_open_epoch_seconds", "bar_open_utc",
             "quote_epoch_milliseconds", "quote_time_utc", "bid", "ask",
             "observed_utc", "open", "high", "low", "close", "tick_volume", "real_volume", "spread_points");
   string observed = IsoUtc(TimeGMT());
   for(int i=0; i<copied; i++)
   {
      // CopyRates(start_pos=1) excludes the forming candle. MT5 volume is
      // preserved as tick_volume; it is not described as exchange volume.
      // Preserve the raw datetime epoch and render it as UTC. Never apply the
      // current broker offset to historical bars: broker DST rules can change.
      FileWrite(file, InpConfirmedGoldSymbol, "M15", (long)rates[i].time, IsoUtc(rates[i].time),
                quote.time_msc, IsoUtcMillis(quote.time_msc), DoubleToString(quote.bid, _Digits),
                DoubleToString(quote.ask, _Digits), observed,
                DoubleToString(rates[i].open, _Digits), DoubleToString(rates[i].high, _Digits),
                DoubleToString(rates[i].low, _Digits), DoubleToString(rates[i].close, _Digits),
                (long)rates[i].tick_volume, (long)rates[i].real_volume, (int)rates[i].spread);
   }
   // A footer lets the local reader detect a partial file during a rewrite.
   FileWrite(file, "#SNAPSHOT_END", observed, copied);
   FileFlush(file);
   FileClose(file);
   g_lastClosedBar = newest;
   PrintFormat("GoldPrecision local snapshot exported: symbol=%s M15 rows=%d closed_bar_utc=%s",
               InpConfirmedGoldSymbol, copied, IsoUtc(newest));
   return true;
}

int OnInit()
{
   if(InpTimerSeconds < 5 || InpTimerSeconds > 300)
      return INIT_PARAMETERS_INCORRECT;
   EventSetTimer(InpTimerSeconds);
   ExportClosedM15();
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}

void OnTimer()
{
   ExportClosedM15();
}
