"use strict";
const a=require("node:assert/strict");
const {inspect,summarise,empty}=require("./review_paper_report_bridge");
const {validatePaperReport}=require("../review-dashboard");
const missing=inspect({authenticated:false,databasePath:""});
a.equal(missing.statusCode,200);
a.equal(missing.body.status,"NO_PERSISTENT_PAPER_JOURNAL_CONNECTED");
a.equal(missing.body.closedTrades,0);
a.equal(missing.body.winRate,null);
a.equal(missing.body.netModeledUsd,null);
a.equal(missing.body.signal,"WAIT");
a.equal(missing.body.liveOrdersAllowed,false);
a.equal(missing.body.providerRequestsMade,0);
a.equal(validatePaperReport(missing.body)?.connected,false);
const auth=inspect({authenticated:false,databasePath:"/unused/test.sqlite3"});
a.equal(auth.statusCode,401);
a.equal(auth.body.status,"PRIVATE_VIEWER_SESSION_REQUIRED");
a.equal(auth.body.netModeledUsd,null);
const badFile=inspect({authenticated:true,databasePath:"/not-an-existing-db-20390101.sqlite3"});
a.equal(badFile.statusCode,503);
a.equal(badFile.body.status,"PRIVATE_PAPER_JOURNAL_UNVERIFIED");
a.equal(badFile.body.signal,"WAIT");
const missingStats={
 closedTrades:0,netModeledUsd:null,modeledCostsUsd:null,
 netDoubleCostStressUsd:null,averageNetR:null,winRate:null,
 maxClosedDrawdownUsd:null,profitFactor:null,
 outcomeStatus:"NO_CLOSED_PAPER_TRADES",independentlyValidated:false
};
const good={
 mode:"GOLD_OFFLINE_SYNTHETIC_PAPER_REPORTS_V1",
 status:"OFFLINE_SYNTHETIC_DESCRIPTIVE_ONLY",
 origin:"OFFLINE_SYNTHETIC_FORWARD_PAPER_JOURNAL_V1",
 signal:"WAIT",executable:false,
 independentHoldoutValidated:false,
 realMarketDataConnected:false,brokerTransactionCostsVerified:false,
 statisticallyValidated:false,paperOrderExecutionEnabled:false,
 liveOrderExecutionEnabled:false,providerRequestsMade:0,
 brokerOrdersSent:0,paperOrdersSent:0,
 unverifiedNextM15ForecastAccuracy:null,
 journalRows:0,cumulative:missingStats,
 dailyUTC:[],weeklyUTC:[],completedFiveTradeBatches:[],
 partialFiveTradeBatchCount:0,firstHundredClosedTradeCheckpoint:null,
 secret:"DO_NOT_EXPOSE_PRIVATE_OR_RAW"
};
const clean=summarise(good);
a.equal(clean.status,"SYNTHETIC_LOCAL_RESULTS_NOT_REAL_MARKET");
a.equal(clean.privateJournalConnected,true);
a.equal(clean.closedTrades,0);
a.equal(clean.winRate,null);
a.equal(clean.signal,"WAIT");
a.equal(validatePaperReport(clean)?.connected,true);
a(!JSON.stringify(clean).includes("DO_NOT_EXPOSE_PRIVATE_OR_RAW"));
for(const fake of [
 {...good,signal:"BUY"},
 {...good,executable:true},
 {...good,independentHoldoutValidated:true},
 {...good,unverifiedNextM15ForecastAccuracy:1},
 {...good,paperOrderExecutionEnabled:true},
 {...good,liveOrderExecutionEnabled:true},
 {...good,providerRequestsMade:1},
 {...good,firstHundredClosedTradeCheckpoint:missingStats},
 {...good,journalRows:-1},
 {...good,cumulative:{...missingStats,closedTrades:1}},
 {...good,cumulative:{...missingStats,winRate:1}},
 {...good,weeklyUTC:[{...missingStats,utcStart:"2026-11-16"}]},
 {...good,dailyUTC:[{...missingStats,utcStart:"2026-11-18"}]},
]){
 a.equal(summarise(fake),null);
}
for(const fake of [
 {...missing.body,closedTrades:1},
 {...missing.body,privateJournalConnected:true},
 {...missing.body,winRate:0.99},
 {...missing.body,providerRequestsMade:1},
 {...missing.body,signal:"SELL"},
 {...missing.body,liveOrdersAllowed:true},
 {...clean,independentHoldoutValidated:true},
 {...clean,signal:"BUY"}
]){
 a.equal(validatePaperReport(fake),null);
}
a.equal(empty().mode,"GOLD_PRIVATE_OFFLINE_PAPER_REPORT_BRIDGE_V1");
console.log("PASS private no-ledger 200, anonymous 401 when connected, read-only 503, synthetic WAIT UI veto and no raw paper data");
