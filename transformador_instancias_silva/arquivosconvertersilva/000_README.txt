Information about data fields present in instance files.
-----------------------------------------------------------------------
Clients:
Number of maritime platforms.
-----------------------------------------------------------------------
Orders:
Number of orders.
-----------------------------------------------------------------------
Vehicles:
Number of platform supply vessels (PSV).
-----------------------------------------------------------------------
Threshold distance:
Distance at which the velocity of a PSV changes. Given in kilometers.
-----------------------------------------------------------------------
Vehicles information:

ID: vehicle identifier.

DC: deck cargo commodity. Given in squared meters.

D: diesel commodity. Given in cubic meters.

W: water commodity. Given in cubic meters.

DWT: dead weight tonnage of the PSV. It is the vessel’s size. Given in tons.

VL: low velocity value that applies while the distance to be traveled by a PSV is smaller than the threshold distance. Given in kilometers per hour.

VH: high velocity value that applies while the distance to be traveled by a PSV is greater than the threshold distance. Given in kilometers per hour.

FCA: fuel cost for a PSV anchored at the supply base’s vicinity area. Given in USD per hour.

FCB: fuel cost for a PSV at the supply base. Given in USD per hour.

FCN: fuel cost for a PSV in navigation. Given in USD per hour.

FCS: fuel cost for a PSV in service. Given in USD per hour.

SP: safe positioning time. Given in hours. Note: safe positioning consumes fuel according to FCS.

TRI: maximum number of trips a vessel can perform.

TDL: trip duration limit. Given in hours.

ETR: estimated time of readiness. It is the moment a PSV turns available for use. Given in hours.
-----------------------------------------------------------------------
Clients information:

ID: client identifier.

LON: longitude.

LAT: latitude.

DCP: deck cargo pickup. Deck cargo order’s amount in squared meters that should be picked up. Given in squared meters.

DCD: deck cargo delivery. Deck cargo order’s amount in squared meters that should be delivered. Given in squared meters.

DD: diesel delivery. Diesel order’s amount in cubic meters that should be delivered. Given in cubic meters.

WD: water delivery. Water order’s amount in cubic meters that should be delivered. Given in cubic meters.

DCP_Ef: efficiency to operate pickup orders of deck cargo. Given in hours per squared meter.

DCD_Ef: efficiency to operate delivery orders of deck cargo. Given in hours per squared meter.

DD_Ef: efficiency to operate delivery orders of diesel. Given in hours per squared meter.

WD_Ef: efficiency to operate delivery orders of water. Given in hours per squared meter. Usage example: in instance “20n-4k-7c-244r_SSML”, the platform with ID=7 ordered 381 m^3 of water; considering the efficiency WL_Ef = 0.0179 h/m^3 that such platform develops, the service time to deliver that volume of water will be 381 * 0.0179 = 6.82 h. Similar calculations are valid for other order and efficiency values for a platform. At the supply base, the service time will depend on the orders carried by a PSV.

SET: setup time. Given in hours. Note: setup consumes fuel according to FCS.

ET: earliest time for a time window. ET0, ET1, … , ETn mean the earliest moments for each of the “n” time windows available. Given in hours.

LT: latest time for a time window. LT0, LT1, … , LTn mean the latest moments for each of the “n” time windows available. Given in hours.
-----------------------------------------------------------------------
Orders information:

ID: client identifier.

Commodity/Quantity/Deadline: tuple that indicates the commodity type, quantity, and deadline per order. Example: in instance “20n-4k-7c-244r_SSML”, the platform with ID=1 placed three orders, represented by “DCP/-27/120”, “DCD/18/120”, “DD/336/168”. The first order means pickup of deck cargo with amount 27 m^2 (pickups by convention have negative signal) to be finished within 120 hours. The second order means delivery of deck cargo with amount 18 m^2 (deliveries by convention are positive) to be finished within 120 hours. The third order can be read similarly.
-----------------------------------------------------------------------
Capacity commodity assignment:

CAP: PSV’s compartment net capacity. The capacity-commodity assignment matrix just informs what commodity goes in what compartment. For example, in instance “20n-4k-7c-244r_SSML”, we have that orders of DCP and DCD use the compartment for deck cargo (DC); orders of DD use the compartment for diesel (D); and orders of WD use the compartment for water (W). Deck cargo capacity is given in m^2, while diesel and water in m^3.
