describe("Basic loading tests for test nexus file", () => {
  beforeEach(() => {
    cy.visit("http://localhost:3000/view/mari/20024/MAR29531_10.5meV_sa.nxspe");
  });

  it("loads the canvas area", () => {
    cy.get("[class*=canvasArea]")
      .should("be.visible")
      .find("canvas")
      .should("be.visible");
  });
});
