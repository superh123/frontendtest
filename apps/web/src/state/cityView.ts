import {create} from 'zustand';
// View-only state. No simulation tick, branch, or financial values live here.
export const useCityView=create<{lod:0|1|2|3;zoomed:boolean;districtFilter:string|null;focusLabel:string|null;setDistrict:(district:string|null)=>void}>(set=>({lod:0,zoomed:false,districtFilter:null,focusLabel:null,setDistrict:districtFilter=>set({districtFilter})}));
