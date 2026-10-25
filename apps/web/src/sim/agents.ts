export type Household = {id:string;district:string;archetype:'mortgaged'|'renter'|'outright'|'saver';income:number;savings:number;mortgageBalance:number;mortgageRate:number;mortgageVariable:boolean;rent:number;debt:number;employerId:string|null;bankId:string;bufferTarget:number;riskAversion:number};
export type Firm={id:string;district:string;sector:string;cash:number;inventory:number;staff:number;price:number;revenueLastTick:number;loanBalance:number;bankId:string;open:boolean};
export type Bank={id:string;district:string;deposits:number;loansOut:number;capital:number;baseRate:number};
export type LedgerEntry={id:string;tick:number;fromId:string;toId:string;amount:number;kind:'wage'|'rent'|'mortgage'|'purchase'|'loan'|'interest'|'tax'|'transfer';eventId:string};
