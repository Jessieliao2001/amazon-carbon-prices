from pysrc.services.get_opt import get_optimization
from pysrc.analysis.figures import trajectory_diff
from pysrc.analysis.tables import transfer_cost,ambiguity_decom
from pysrc.analysis.map import spatial_allocation
from pysrc.analysis.figures import density


## Section 7.3 Results with robustness to parameter uncertainty

pee_xi_0p5 = 2.8
pee_xi_1 = 4.8
pee_xi_2 = 5.6
pee_xi_10000 = 6.8

# ## xi1
# get_optimization(num_sites=1043,pee=pee_xi_10000,model="det",solver="gurobi")
# get_optimization(num_sites=1043,pee=pee_xi_1,model="hmc",xi=1.0,solver="gurobi")
# get_optimization(num_sites=1043,pee=pee_xi_10000,model="hmc",xi=1.0,solver="gurobi")

# ambiguity_decom(num_sites=1043,pe_det=pee_xi_10000,pe_hmc=pee_xi_1,xi=1.0,solver="gurobi") 
# trajectory_diff(num_sites=1043,pe_hmc=pee_xi_10000,pe_det=pee_xi_10000,b=0,solver="gurobi",pa=41.11,xi=1.0) # Figure 11
trajectory_diff(num_sites=1043,pe_hmc=pee_xi_1,pe_det=pee_xi_10000,b=0,solver="gurobi",pa=41.11,xi=1.0) # Figure 14
trajectory_diff(num_sites=1043,pe_hmc=pee_xi_1,pe_det=pee_xi_10000,b=15,solver="gurobi",pa=41.11,xi=1.0) # Figure 14

# transfer_cost(num_sites=1043,pee=pee_xi_1,xi=1.0,solver="gurobi",y=30,model="hmc") 
# transfer_cost(num_sites=1043,pee=pee_xi_1,xi=1.0,solver="gurobi",y=15,model="hmc") 


# spatial_allocation(num_sites=1043,pe_hmc=pee_xi_10000,pe_det=pee_xi_10000,xi=1.0,solver="gurobi",b=0) # Figure 12
# spatial_allocation(num_sites=1043,pe_hmc=pee_xi_1,pe_det=pee_xi_10000,xi=1.0,solver="gurobi",b=0) 
# spatial_allocation(num_sites=1043,pe_hmc=pee_xi_1,pe_det=pee_xi_10000,xi=1.0,solver="gurobi",b=15) 





# # xi0_5
# get_optimization(num_sites=1043,pee=pee_xi_0p5,model="hmc",xi=0.5,solver="gurobi")
# ambiguity_decom(num_sites=1043,pe_det=pee_xi_10000,pe_hmc=pee_xi_0p5,xi=0.5,solver="gurobi") 



# # xi2
# get_optimization(num_sites=1043,pee=pee_xi_2,model="hmc",xi=2.0,solver="gurobi")
# ambiguity_decom(num_sites=1043,pe_det=pee_xi_10000,pe_hmc=pee_xi_2,xi=2.0,solver="gurobi") 


# density(num_sites=1043,pee=pee_xi_1,xi=1.0,solver="gurobi")
# density(num_sites=1043,pee=pee_xi_2,xi=2.0,solver="gurobi")
# density(num_sites=1043,pee=pee_xi_0p5,xi=0.5,solver="gurobi")


print("hmc All done!")


